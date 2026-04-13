from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse

from .models import ListaCanais, ListaApp, Servidor, AppIPTV, Plano
from .forms import ListaCanaisForm, ListaAppForm, ServidorForm, AppIPTVForm, PlanoForm


class ListaCanaisListView(LoginRequiredMixin, ListView):
    model = ListaCanais
    template_name = 'listas/lista.html'
    context_object_name = 'listas'

    def get_queryset(self):
        qs = ListaCanais.objects.select_related('cliente', 'servidor', 'pagador')
        q = self.request.GET.get('q', '')
        status = self.request.GET.get('status', '')
        if q:
            qs = qs.filter(nome__icontains=q) | ListaCanais.objects.filter(cliente__nome__icontains=q)
        if status == 'ativa':
            qs = qs.filter(ativa=True)
        elif status == 'inativa':
            qs = qs.filter(ativa=False)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['status_filtro'] = self.request.GET.get('status', '')
        return ctx


def _planos_json():
    import json
    dados = {
        str(p.pk): {
            'preco': float(p.preco_por_tela),
            'custo': float(p.custo_por_tela),
            'nome': p.nome,
        }
        for p in Plano.objects.filter(ativo=True)
    }
    return json.dumps(dados)


class ListaCanaisCreateView(LoginRequiredMixin, CreateView):
    model = ListaCanais
    form_class = ListaCanaisForm
    template_name = 'listas/form.html'

    def _cliente_fixo(self):
        from clientes.models import Cliente
        cliente_id = self.request.GET.get('cliente')
        if cliente_id:
            try:
                return Cliente.objects.get(pk=cliente_id)
            except Cliente.DoesNotExist:
                pass
        return None

    def get_initial(self):
        initial = super().get_initial()
        cliente = self._cliente_fixo()
        if cliente:
            initial['cliente'] = cliente
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nova Lista de Canais'
        ctx['btn_label'] = 'Cadastrar Lista'
        ctx['planos_json'] = _planos_json()
        cliente = self._cliente_fixo()
        if cliente:
            ctx['cliente_fixo'] = cliente
            ctx['cancel_url'] = reverse('clientes:detalhe', kwargs={'pk': cliente.pk})
        else:
            ctx['cancel_url'] = reverse('listas:lista')
        return ctx

    def form_valid(self, form):
        lista = form.save(commit=False)
        if lista.plano:
            lista.valor_mensalidade = lista.plano.preco_por_tela * lista.num_telas
        lista.save()
        messages.success(self.request, 'Lista cadastrada com sucesso!')
        return redirect(self.get_success_url())

    def get_success_url(self):
        cliente = self._cliente_fixo()
        if cliente:
            return reverse('clientes:detalhe', kwargs={'pk': cliente.pk})
        return reverse('listas:detalhe', kwargs={'pk': self.object.pk})


class ListaCanaisUpdateView(LoginRequiredMixin, UpdateView):
    model = ListaCanais
    form_class = ListaCanaisForm
    template_name = 'listas/form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome}'
        ctx['btn_label'] = 'Salvar Alterações'
        ctx['planos_json'] = _planos_json()
        ctx['cancel_url'] = reverse('clientes:detalhe', kwargs={'pk': self.object.cliente.pk})
        return ctx

    def form_valid(self, form):
        lista = form.save(commit=False)
        if lista.plano:
            lista.valor_mensalidade = lista.plano.preco_por_tela * lista.num_telas
        lista.save()
        messages.success(self.request, 'Lista atualizada com sucesso!')
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('clientes:detalhe', kwargs={'pk': self.object.cliente.pk})


@login_required
def lista_detalhe(request, pk):
    lista = get_object_or_404(
        ListaCanais.objects.select_related('cliente', 'servidor', 'pagador'),
        pk=pk
    )
    apps = lista.apps.select_related('app').all()
    mensalidades = lista.mensalidades.order_by('-vencimento')[:12]
    return render(request, 'listas/detalhe.html', {
        'lista': lista,
        'apps': apps,
        'mensalidades': mensalidades,
    })


@login_required
def lista_excluir(request, pk):
    lista = get_object_or_404(ListaCanais, pk=pk)
    if request.method == 'POST':
        lista.delete()
        messages.success(request, 'Lista excluída com sucesso!')
        return redirect('listas:lista')
    return redirect('listas:detalhe', pk=pk)


# --- Apps por lista ---

@login_required
def lista_app_adicionar(request, lista_pk):
    lista = get_object_or_404(ListaCanais, pk=lista_pk)
    if request.method == 'POST':
        form = ListaAppForm(request.POST, lista=lista)
        if form.is_valid():
            lista_app = form.save(commit=False)
            lista_app.lista = lista
            lista_app.save()
            messages.success(request, 'Aplicativo adicionado!')
            return redirect('listas:detalhe', pk=lista_pk)
    else:
        form = ListaAppForm(lista=lista)
    return render(request, 'listas/app_form.html', {
        'form': form,
        'lista': lista,
        'titulo': f'Adicionar App — {lista.nome}',
        'btn_label': 'Adicionar',
    })


@login_required
def lista_app_editar(request, lista_pk, app_pk):
    lista = get_object_or_404(ListaCanais, pk=lista_pk)
    lista_app = get_object_or_404(ListaApp, pk=app_pk, lista=lista)
    if request.method == 'POST':
        form = ListaAppForm(request.POST, instance=lista_app, lista=lista)
        if form.is_valid():
            form.save()
            messages.success(request, 'Aplicativo atualizado!')
            return redirect('listas:detalhe', pk=lista_pk)
    else:
        form = ListaAppForm(instance=lista_app, lista=lista)
    return render(request, 'listas/app_form.html', {
        'form': form,
        'lista': lista,
        'titulo': f'Editar App — {lista_app.app.nome}',
        'btn_label': 'Salvar',
    })


@login_required
def lista_app_excluir(request, lista_pk, app_pk):
    lista_app = get_object_or_404(ListaApp, pk=app_pk, lista__pk=lista_pk)
    if request.method == 'POST':
        lista_app.delete()
        messages.success(request, 'Aplicativo removido!')
    return redirect('listas:detalhe', pk=lista_pk)


# --- Servidores ---

class ServidorListView(LoginRequiredMixin, ListView):
    model = Servidor
    template_name = 'listas/servidores.html'
    context_object_name = 'servidores'


class ServidorCreateView(LoginRequiredMixin, CreateView):
    model = Servidor
    form_class = ServidorForm
    template_name = 'listas/servidor_form.html'
    success_url = reverse_lazy('listas:servidores')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Servidor'
        ctx['btn_label'] = 'Cadastrar'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Servidor cadastrado!')
        return super().form_valid(form)


class ServidorUpdateView(LoginRequiredMixin, UpdateView):
    model = Servidor
    form_class = ServidorForm
    template_name = 'listas/servidor_form.html'
    success_url = reverse_lazy('listas:servidores')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome}'
        ctx['btn_label'] = 'Salvar'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Servidor atualizado!')
        return super().form_valid(form)


@login_required
def servidor_excluir(request, pk):
    servidor = get_object_or_404(Servidor, pk=pk)
    if request.method == 'POST':
        servidor.delete()
        messages.success(request, 'Servidor excluído!')
    return redirect('listas:servidores')


# --- Aplicativos IPTV ---

class AppIPTVListView(LoginRequiredMixin, ListView):
    model = AppIPTV
    template_name = 'listas/aplicativos.html'
    context_object_name = 'aplicativos'


class AppIPTVCreateView(LoginRequiredMixin, CreateView):
    model = AppIPTV
    form_class = AppIPTVForm
    template_name = 'listas/app_iptv_form.html'
    success_url = reverse_lazy('listas:aplicativos')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Aplicativo'
        ctx['btn_label'] = 'Cadastrar'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Aplicativo cadastrado!')
        return super().form_valid(form)


class AppIPTVUpdateView(LoginRequiredMixin, UpdateView):
    model = AppIPTV
    form_class = AppIPTVForm
    template_name = 'listas/app_iptv_form.html'
    success_url = reverse_lazy('listas:aplicativos')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome}'
        ctx['btn_label'] = 'Salvar'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Aplicativo atualizado!')
        return super().form_valid(form)


@login_required
def app_iptv_excluir(request, pk):
    app = get_object_or_404(AppIPTV, pk=pk)
    if request.method == 'POST':
        app.delete()
        messages.success(request, 'Aplicativo excluído!')
    return redirect('listas:aplicativos')


# --- Planos ---

class PlanoListView(LoginRequiredMixin, ListView):
    model = Plano
    template_name = 'listas/planos.html'
    context_object_name = 'planos'


class PlanoCreateView(LoginRequiredMixin, CreateView):
    model = Plano
    form_class = PlanoForm
    template_name = 'listas/plano_form.html'
    success_url = reverse_lazy('listas:planos')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Plano'
        ctx['btn_label'] = 'Cadastrar'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Plano cadastrado!')
        return super().form_valid(form)


class PlanoUpdateView(LoginRequiredMixin, UpdateView):
    model = Plano
    form_class = PlanoForm
    template_name = 'listas/plano_form.html'
    success_url = reverse_lazy('listas:planos')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object.nome}'
        ctx['btn_label'] = 'Salvar'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Plano atualizado!')
        return super().form_valid(form)


@login_required
def plano_excluir(request, pk):
    plano = get_object_or_404(Plano, pk=pk)
    if request.method == 'POST':
        plano.delete()
        messages.success(request, 'Plano excluído!')
    return redirect('listas:planos')


# --- Filtros ---

def _checar_dns(url_str):
    """
    Tenta conexão TCP na porta do servidor.
    Qualquer resposta HTTP (mesmo 401/403/404) = online.
    Timeout ou recusa de conexão = offline.
    """
    import socket
    import urllib.parse
    # Normaliza: se não tem esquema, adiciona http://
    if not url_str.startswith('http'):
        url_str = 'http://' + url_str
    parsed = urllib.parse.urlparse(url_str)
    host = parsed.hostname or ''
    port = parsed.port or 80
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        return True
    except Exception:
        return False


@login_required
def servidor_ping(request, pk):
    from django.http import JsonResponse
    servidor = get_object_or_404(Servidor, pk=pk)
    url = f'{servidor.dns}:{servidor.porta}'
    online = _checar_dns(url)
    return JsonResponse({'online': online, 'url': url})


@login_required
def dns_health_check(request):
    """Verifica todos os DNS em uso e retorna JSON com status de cada um."""
    from django.http import JsonResponse
    from concurrent.futures import ThreadPoolExecutor

    dns_map = {}
    for s in Servidor.objects.filter(ativo=True):
        key = f'{s.dns}:{s.porta}'
        dns_map[key] = s.nome
    for dns_custom in (ListaCanais.objects
                       .filter(ativa=True)
                       .exclude(dns_customizado='')
                       .values_list('dns_customizado', flat=True)
                       .distinct()):
        if dns_custom not in dns_map:
            dns_map[dns_custom] = dns_custom

    def checar(item):
        url, nome = item
        return {'url': url, 'nome': nome, 'online': _checar_dns(url)}

    with ThreadPoolExecutor(max_workers=10) as ex:
        resultados = list(ex.map(checar, dns_map.items()))

    return JsonResponse({'resultados': resultados})


@login_required
def filtrar_por_app(request):
    apps = AppIPTV.objects.all()
    app_id = request.GET.get('app', '')
    listas = ListaCanais.objects.none()
    app_selecionado = None

    if app_id:
        try:
            app_selecionado = AppIPTV.objects.get(pk=app_id)
            listas = (
                ListaCanais.objects
                .filter(apps__app=app_selecionado, ativa=True)
                .select_related('cliente', 'servidor')
                .order_by('cliente__nome')
            )
        except AppIPTV.DoesNotExist:
            pass

    return render(request, 'listas/filtro_app.html', {
        'apps': apps,
        'app_selecionado': app_selecionado,
        'app_id': app_id,
        'listas': listas,
    })


@login_required
def filtrar_por_servidor(request):
    from django.db.models import Q

    # Monta dict de todos os DNS únicos em uso: dns_string -> label
    opcoes_dns = {}
    for s in Servidor.objects.filter(ativo=True):
        key = f'{s.dns}:{s.porta}'
        opcoes_dns[key] = f'{s.nome} — {key}'
    for dns in (ListaCanais.objects
                .filter(ativa=True)
                .exclude(dns_customizado='')
                .values_list('dns_customizado', flat=True)
                .distinct()):
        if dns not in opcoes_dns:
            opcoes_dns[dns] = f'{dns} (personalizado)'

    dns_escolhido = request.GET.get('dns', '')
    listas = ListaCanais.objects.none()

    if dns_escolhido:
        # Listas com dns_customizado igual ao escolhido
        q = Q(dns_customizado=dns_escolhido)
        # Listas sem dns_customizado cujo servidor resulta no mesmo DNS
        for s in Servidor.objects.all():
            if f'{s.dns}:{s.porta}' == dns_escolhido:
                q |= Q(servidor=s, dns_customizado='')
        listas = (
            ListaCanais.objects
            .filter(q, ativa=True)
            .select_related('cliente', 'servidor')
            .order_by('cliente__nome')
        )

    return render(request, 'listas/filtro_servidor.html', {
        'opcoes_dns': opcoes_dns,
        'dns_escolhido': dns_escolhido,
        'listas': listas,
    })
