from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from datetime import date, timedelta
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count, Q

from .models import Cliente, Pagador, TemplateMensagem
from .forms import ClienteForm, PagadorForm
from listas.models import ListaCanais
from financeiro.models import Mensalidade


def gerar_proximas_mensalidades():
    """
    Garante que cada lista ativa tenha uma mensalidade pendente/futura.
    Chamado no dashboard para manter a lista sempre atualizada.
    """
    from listas.models import add_one_month

    hoje = date.today()

    # Primeiro: atualiza pendentes vencidas para atrasado
    Mensalidade.objects.filter(status='pendente', vencimento__lt=hoje).update(status='atrasado')

    # Para cada lista ativa com data_ativacao
    for lista in ListaCanais.objects.filter(ativa=True, data_ativacao__isnull=False):
        ultima = lista.mensalidades.order_by('-vencimento').first()

        if ultima is None:
            # Nunca teve mensalidade — cria com a data de ativação
            # Se a data de ativação já passou, usa hoje para não gerar retroativo
            proxima = max(lista.data_ativacao, hoje)
        elif ultima.status == 'pago':
            # Última foi paga — gera a do próximo mês
            proxima = add_one_month(ultima.vencimento)
        else:
            # Tem uma pendente/atrasada — não gera nova
            continue

        # Não cria mensalidade retroativa: evita gerar registro que já venceu
        # e seria imediatamente marcado como atrasado pelo save() do model
        if proxima < hoje:
            continue

        # Só cria se ainda não existe mensalidade para esse vencimento
        if not lista.mensalidades.filter(vencimento=proxima).exists():
            Mensalidade.objects.create(
                lista=lista,
                valor=lista.valor_mensalidade,
                vencimento=proxima,
                referencia=proxima.strftime('%Y-%m'),
                status='pendente',
            )


@login_required
def dashboard(request):
    hoje = date.today()
    sete_dias = hoje + timedelta(days=7)

    gerar_proximas_mensalidades()

    total_clientes = Cliente.objects.filter(ativo=True).count()
    total_listas = ListaCanais.objects.filter(ativa=True).count()
    total_atrasadas = Mensalidade.objects.filter(status='atrasado').count()

    # Financeiro do mês atual
    mensalidades_pagas_mes = Mensalidade.objects.filter(
        status='pago',
        data_pagamento__year=hoje.year,
        data_pagamento__month=hoje.month,
    )
    pagas_mes = mensalidades_pagas_mes.count()
    receita_mes = mensalidades_pagas_mes.aggregate(t=Sum('valor'))['t'] or 0

    # Custo estimado: listas ativas com plano definido
    custo_mes = (
        ListaCanais.objects
        .filter(ativa=True, plano__isnull=False)
        .annotate(custo_lista=ExpressionWrapper(
            F('plano__custo_por_tela') * F('num_telas'),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        ))
        .aggregate(t=Sum('custo_lista'))['t'] or 0
    )
    lucro_mes = receita_mes - custo_mes

    alertas_atrasadas = (
        Mensalidade.objects
        .filter(status='atrasado')
        .select_related('lista__cliente', 'lista__servidor')
        .order_by('vencimento')[:15]
    )
    alertas_vencendo = (
        Mensalidade.objects
        .filter(status='pendente', vencimento__gte=hoje, vencimento__lte=sete_dias)
        .select_related('lista__cliente')
        .order_by('vencimento')[:15]
    )

    listas_em_teste = (
        ListaCanais.objects
        .filter(ativa=True, em_teste=True)
        .select_related('cliente')
        .order_by('data_inicio_teste')
    )

    # DNS únicos em uso para o painel de saúde
    from listas.models import Servidor
    dns_saude = {}
    for s in Servidor.objects.filter(ativo=True):
        key = f'{s.dns}:{s.porta}'
        dns_saude[key] = s.nome
    for dns_custom in (ListaCanais.objects
                       .filter(ativa=True)
                       .exclude(dns_customizado='')
                       .values_list('dns_customizado', flat=True)
                       .distinct()):
        if dns_custom not in dns_saude:
            dns_saude[dns_custom] = dns_custom
    dns_saude_list = [{'url': k, 'nome': v} for k, v in dns_saude.items()]

    # Receita dos últimos 6 meses para o gráfico
    import json
    meses_labels = []
    meses_receita = []
    for i in range(5, -1, -1):
        mes_ref = hoje.replace(day=1) - timedelta(days=i * 30)
        label = mes_ref.strftime('%b/%y')
        receita_m = Mensalidade.objects.filter(
            status='pago',
            data_pagamento__year=mes_ref.year,
            data_pagamento__month=mes_ref.month,
        ).aggregate(t=Sum('valor'))['t'] or 0
        meses_labels.append(label)
        meses_receita.append(float(receita_m))
    grafico_labels = json.dumps(meses_labels)
    grafico_receita = json.dumps(meses_receita)

    return render(request, 'dashboard.html', {
        'total_clientes': total_clientes,
        'total_listas': total_listas,
        'pagas_mes': pagas_mes,
        'total_atrasadas': total_atrasadas,
        'receita_mes': receita_mes,
        'custo_mes': custo_mes,
        'lucro_mes': lucro_mes,
        'alertas_atrasadas': alertas_atrasadas,
        'alertas_vencendo': alertas_vencendo,
        'listas_em_teste': listas_em_teste,
        'grafico_labels': grafico_labels,
        'grafico_receita': grafico_receita,
        'dns_saude_list': dns_saude_list,
        'tpl_atrasado': TemplateMensagem.get_template('atrasado'),
        'tpl_vencendo': TemplateMensagem.get_template('vencendo'),
        'tpl_teste': TemplateMensagem.get_template('teste'),
        'hoje': hoje,
    })


@login_required
def configurar_mensagens(request):
    tipos = ['atrasado', 'vencendo', 'teste']

    if request.method == 'POST':
        for tipo in tipos:
            mensagem = request.POST.get(f'mensagem_{tipo}', '').strip()
            if mensagem:
                TemplateMensagem.objects.update_or_create(
                    tipo=tipo,
                    defaults={'mensagem': mensagem}
                )
        messages.success(request, 'Templates salvos com sucesso!')
        return redirect('configurar_mensagens')

    templates = {}
    for tipo in tipos:
        templates[tipo] = TemplateMensagem.get_template(tipo)

    return render(request, 'configurar_mensagens.html', {
        'templates': templates,
        'variaveis': TemplateMensagem.VARIAVEIS,
        'choices': dict(TemplateMensagem.TIPO_CHOICES),
    })


@login_required
def encerrar_teste(request, lista_pk):
    from listas.models import ListaCanais
    lista = get_object_or_404(ListaCanais, pk=lista_pk)
    if request.method == 'POST':
        lista.em_teste = False
        lista.data_inicio_teste = None
        lista.save()
        messages.success(request, f'Teste de {lista.cliente.nome_tratamento} encerrado. Lista marcada como ativa.')
    return redirect('/')


@login_required
def busca_global(request):
    q = request.GET.get('q', '').strip()
    clientes_r = []
    listas_r = []
    if q:
        clientes_r = Cliente.objects.filter(
            Q(nome__icontains=q) | Q(whatsapp__icontains=q) | Q(apelido__icontains=q)
        ).order_by('nome')[:20]
        listas_r = ListaCanais.objects.filter(
            Q(nome__icontains=q) | Q(usuario__icontains=q) | Q(cliente__nome__icontains=q)
        ).select_related('cliente').order_by('cliente__nome')[:20]
    return render(request, 'busca.html', {'q': q, 'clientes_r': clientes_r, 'listas_r': listas_r})


# --- Clientes ---

class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clientes/lista.html'
    context_object_name = 'clientes'

    def get_queryset(self):
        qs = Cliente.objects.prefetch_related('listas')
        q = self.request.GET.get('q', '')
        if q:
            qs = qs.filter(nome__icontains=q) | Cliente.objects.filter(whatsapp__icontains=q)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Cliente'
        ctx['btn_label'] = 'Cadastrar Cliente'
        return ctx

    def form_valid(self, form):
        cliente = form.save()

        # Cria pagador junto se informado
        if form.cleaned_data.get('tem_pagador_diferente') and form.cleaned_data.get('pagador_nome'):
            Pagador.objects.create(
                nome=form.cleaned_data['pagador_nome'],
                whatsapp=form.cleaned_data.get('pagador_whatsapp', ''),
                notas=f'Pagador de {cliente.nome}',
            )
            messages.success(self.request, f'Cliente e pagador cadastrados com sucesso!')
        else:
            messages.success(self.request, 'Cliente cadastrado com sucesso!')

        return redirect('clientes:detalhe', pk=cliente.pk)


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome}'
        ctx['btn_label'] = 'Salvar Alterações'
        ctx['editando'] = True
        return ctx

    def form_valid(self, form):
        cliente = form.save()

        if form.cleaned_data.get('tem_pagador_diferente') and form.cleaned_data.get('pagador_nome'):
            Pagador.objects.create(
                nome=form.cleaned_data['pagador_nome'],
                whatsapp=form.cleaned_data.get('pagador_whatsapp', ''),
                notas=f'Pagador de {cliente.nome}',
            )
            messages.success(self.request, 'Cliente atualizado e pagador adicionado!')
        else:
            messages.success(self.request, 'Cliente atualizado com sucesso!')

        return redirect('clientes:detalhe', pk=cliente.pk)


@login_required
def cliente_excluir(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.delete()
        messages.success(request, f'Cliente {cliente.nome} excluído.')
    return redirect('clientes:lista')


@login_required
def cliente_detalhe(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    listas = cliente.listas.select_related('servidor', 'pagador').prefetch_related('apps__app').all()
    return render(request, 'clientes/detalhe.html', {
        'cliente': cliente,
        'listas': listas,
    })


# --- Pagadores ---

class PagadorListView(LoginRequiredMixin, ListView):
    model = Pagador
    template_name = 'clientes/pagadores.html'
    context_object_name = 'pagadores'


class PagadorCreateView(LoginRequiredMixin, CreateView):
    model = Pagador
    form_class = PagadorForm
    template_name = 'clientes/pagador_form.html'
    success_url = reverse_lazy('clientes:pagadores')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Pagador'
        ctx['btn_label'] = 'Cadastrar Pagador'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Pagador cadastrado com sucesso!')
        return super().form_valid(form)


class PagadorUpdateView(LoginRequiredMixin, UpdateView):
    model = Pagador
    form_class = PagadorForm
    template_name = 'clientes/pagador_form.html'
    success_url = reverse_lazy('clientes:pagadores')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome}'
        ctx['btn_label'] = 'Salvar Alterações'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Pagador atualizado com sucesso!')
        return super().form_valid(form)


@login_required
def pagador_excluir(request, pk):
    pagador = get_object_or_404(Pagador, pk=pk)
    if request.method == 'POST':
        pagador.delete()
        messages.success(request, 'Pagador excluído.')
    return redirect('clientes:pagadores')


# --- Relatórios ---

@login_required
def relatorios(request):
    hoje = date.today()
    dias = int(request.GET.get('dias', 7))
    limite = hoje + timedelta(days=dias)

    vencendo = (
        Mensalidade.objects
        .filter(status='pendente', vencimento__gte=hoje, vencimento__lte=limite)
        .select_related('lista__cliente', 'lista__servidor')
        .order_by('vencimento')
    )

    atrasadas = (
        Mensalidade.objects
        .filter(status='atrasado')
        .select_related('lista__cliente')
        .order_by('vencimento')
    )

    total_listas = ListaCanais.objects.filter(ativa=True).count()

    por_servidor = (
        ListaCanais.objects
        .filter(ativa=True)
        .values('servidor__nome')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    por_aparelho = (
        ListaCanais.objects
        .filter(ativa=True)
        .exclude(aparelho='')
        .values('aparelho')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    sem_aparelho = ListaCanais.objects.filter(ativa=True, aparelho='').count()

    # Receita dos últimos 6 meses agrupada por referência
    receita_por_mes = (
        Mensalidade.objects
        .filter(status='pago')
        .values('referencia')
        .annotate(qtd=Count('id'), total=Sum('valor'))
        .order_by('-referencia')[:6]
    )
    # Formata referência YYYY-MM → Mês/Ano
    import calendar
    meses_pt = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    receita_formatada = []
    for row in receita_por_mes:
        try:
            ano, mes = row['referencia'].split('-')
            label = f"{meses_pt[int(mes)]}/{ano}"
        except Exception:
            label = row['referencia']
        receita_formatada.append({'mes': label, 'qtd': row['qtd'], 'total': row['total']})

    return render(request, 'relatorios.html', {
        'dias': dias,
        'vencendo': vencendo,
        'atrasadas': atrasadas,
        'total_listas': total_listas,
        'por_servidor': por_servidor,
        'por_aparelho': por_aparelho,
        'sem_aparelho': sem_aparelho,
        'receita_por_mes': receita_formatada,
    })
