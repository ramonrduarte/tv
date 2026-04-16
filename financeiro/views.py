from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.utils import timezone

from .models import Mensalidade
from .forms import MensalidadeForm
from listas.models import ListaCanais


class MensalidadeListView(LoginRequiredMixin, ListView):
    model = Mensalidade
    template_name = 'financeiro/lista.html'
    context_object_name = 'mensalidades'
    paginate_by = 30

    SORT_FIELDS = {
        'cliente': 'lista__cliente__nome',
        'lista': 'lista__nome',
        'vencimento': 'vencimento',
        'pagamento': 'data_pagamento',
        'valor': 'valor',
        'status': 'status',
    }

    def get_queryset(self):
        hoje = timezone.now().date()
        # Atualiza pendentes vencidas
        Mensalidade.objects.filter(status='pendente', vencimento__lt=hoje).update(status='atrasado')

        qs = Mensalidade.objects.select_related('lista__cliente', 'lista__servidor')
        status = self.request.GET.get('status', '')
        q = self.request.GET.get('q', '')
        mes = self.request.GET.get('mes', '')

        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(lista__cliente__nome__icontains=q) | Mensalidade.objects.filter(lista__nome__icontains=q)
        if mes:
            qs = qs.filter(referencia=mes)

        sort = self.request.GET.get('sort', 'vencimento')
        direction = self.request.GET.get('dir', 'desc')
        orm_field = self.SORT_FIELDS.get(sort, 'vencimento')
        if direction == 'desc':
            orm_field = '-' + orm_field

        return qs.distinct().order_by(orm_field)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_filtro'] = self.request.GET.get('status', '')
        ctx['q'] = self.request.GET.get('q', '')
        ctx['mes'] = self.request.GET.get('mes', '')
        ctx['status_choices'] = Mensalidade.STATUS_CHOICES
        ctx['sort'] = self.request.GET.get('sort', 'vencimento')
        ctx['sort_dir'] = self.request.GET.get('dir', 'desc')
        return ctx


class MensalidadeCreateView(LoginRequiredMixin, CreateView):
    model = Mensalidade
    form_class = MensalidadeForm
    template_name = 'financeiro/form.html'
    success_url = reverse_lazy('financeiro:lista')

    def get_initial(self):
        initial = super().get_initial()
        lista_id = self.request.GET.get('lista')
        if lista_id:
            try:
                lista = ListaCanais.objects.get(pk=lista_id)
                initial['lista'] = lista
                initial['valor'] = lista.valor_mensalidade
            except ListaCanais.DoesNotExist:
                pass
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Registrar Mensalidade'
        ctx['btn_label'] = 'Registrar'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Mensalidade registrada!')
        return super().form_valid(form)

    def get_success_url(self):
        lista_id = self.object.lista.pk
        return reverse('listas:detalhe', kwargs={'pk': lista_id})


class MensalidadeUpdateView(LoginRequiredMixin, UpdateView):
    model = Mensalidade
    form_class = MensalidadeForm
    template_name = 'financeiro/form.html'
    success_url = reverse_lazy('financeiro:lista')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Mensalidade — {self.object.referencia}'
        ctx['btn_label'] = 'Salvar'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Mensalidade atualizada!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('listas:detalhe', kwargs={'pk': self.object.lista.pk})


@login_required
def mensalidade_pagar(request, pk):
    """Marca uma mensalidade como paga com a data de hoje."""
    mensalidade = get_object_or_404(Mensalidade, pk=pk)
    if request.method == 'POST':
        mensalidade.status = 'pago'
        mensalidade.data_pagamento = timezone.now().date()
        mensalidade.save()
        messages.success(request, f'Pagamento de {mensalidade.referencia} registrado!')
    return redirect(request.POST.get('next', reverse('financeiro:lista')))


@login_required
def mensalidade_excluir(request, pk):
    mensalidade = get_object_or_404(Mensalidade, pk=pk)
    lista_pk = mensalidade.lista.pk
    if request.method == 'POST':
        mensalidade.delete()
        messages.success(request, 'Mensalidade excluída!')
    return redirect(reverse('listas:detalhe', kwargs={'pk': lista_pk}))


@login_required
def pagar_lote(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        if ids:
            hoje = timezone.now().date()
            atualizadas = Mensalidade.objects.filter(pk__in=ids).exclude(status='pago')
            total = atualizadas.update(status='pago', data_pagamento=hoje)
            messages.success(request, f'{total} mensalidade(s) marcada(s) como pagas!')
        else:
            messages.warning(request, 'Nenhuma mensalidade selecionada.')
    return redirect(request.POST.get('next', reverse('financeiro:lista')))


@login_required
def exportar_csv(request):
    import csv
    from django.http import HttpResponse
    tipo = request.GET.get('tipo', 'mensalidades')
    response = HttpResponse(content_type='text/csv; charset=utf-8')

    if tipo == 'clientes':
        from clientes.models import Cliente
        response['Content-Disposition'] = 'attachment; filename="clientes.csv"'
        writer = csv.writer(response)
        writer.writerow(['Nome', 'Apelido', 'WhatsApp', 'Status', 'Cadastrado em'])
        for c in Cliente.objects.all().order_by('nome'):
            writer.writerow([c.nome, c.apelido, c.whatsapp,
                             'Ativo' if c.ativo else 'Inativo',
                             c.criado_em.strftime('%d/%m/%Y')])
    else:
        response['Content-Disposition'] = 'attachment; filename="mensalidades.csv"'
        writer = csv.writer(response)
        writer.writerow(['Cliente', 'Lista', 'Referência', 'Vencimento', 'Valor', 'Status', 'Data Pagamento'])
        qs = Mensalidade.objects.select_related('lista__cliente').order_by('-vencimento')
        status = request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        for m in qs:
            writer.writerow([
                m.lista.cliente.nome, m.lista.nome, m.referencia,
                m.vencimento.strftime('%d/%m/%Y'), m.valor, m.get_status_display(),
                m.data_pagamento.strftime('%d/%m/%Y') if m.data_pagamento else '',
            ])
    return response
