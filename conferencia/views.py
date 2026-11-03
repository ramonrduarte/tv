from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from listas.models import ListaCanais

from .leitura import PAINEIS_API, LeituraInvalida, ler_painel, tem_token
from .models import AcessoPainel, ConfiguracaoConferencia, DivergenciaIgnorada, LeituraPainel, VinculoPainel
from .regras import montar_conferencia

NOMES_PAINEL = dict(AcessoPainel.PAINEL_CHOICES)


def _cartao(painel):
    leituras = LeituraPainel.objects.filter(painel=painel)
    return {
        'chave': painel,
        'nome': NOMES_PAINEL[painel],
        'variavel': PAINEIS_API[painel][0],
        'tem_token': tem_token(painel),
        'sucesso': leituras.filter(sucesso=True).first(),
        'ultima': leituras.first(),
    }


@login_required
def painel(request):
    contexto = montar_conferencia()
    contexto.update({
        'paineis': [_cartao(p) for p in PAINEIS_API],
        'configuracao': ConfiguracaoConferencia.atual(),
        'intervalos': ConfiguracaoConferencia.INTERVALO_CHOICES,
    })
    return render(request, 'conferencia/painel.html', contexto)


@login_required
@require_POST
def atualizar(request, painel):
    if painel not in PAINEIS_API:
        raise Http404
    try:
        leitura = ler_painel(painel)
        messages.success(request, f'{NOMES_PAINEL[painel]} lido: {leitura.total} acessos.')
    except LeituraInvalida as e:
        messages.error(request, str(e))
    return redirect('conferencia:painel')


@login_required
@require_POST
def salvar_frequencia(request):
    try:
        horas = int(request.POST.get('intervalo_horas', ''))
    except ValueError:
        horas = None
    if horas in dict(ConfiguracaoConferencia.INTERVALO_CHOICES):
        configuracao = ConfiguracaoConferencia.atual()
        configuracao.intervalo_horas = horas
        configuracao.save()
        messages.success(request, f'Leitura dos painéis: {configuracao.get_intervalo_horas_display().lower()}.')
    else:
        messages.error(request, 'Frequência inválida.')
    return redirect('conferencia:painel')


@login_required
@require_POST
def vincular(request):
    """Só registra o vínculo: não altera login nem senha da lista."""
    acesso = get_object_or_404(AcessoPainel, pk=request.POST.get('acesso_id') or 0)
    lista = ListaCanais.objects.filter(pk=request.POST.get('lista_id') or 0).first()
    if not lista:
        messages.error(request, 'Escolha a lista para vincular.')
    elif not acesso.painel_id:
        messages.error(request, 'Este acesso não tem identificador no painel e é comparado só pelo usuário.')
    elif VinculoPainel.objects.filter(lista=lista).exists():
        messages.error(request, 'Esta lista já está vinculada a outro acesso.')
    elif VinculoPainel.objects.filter(painel=acesso.painel, painel_id=acesso.painel_id).exists():
        messages.error(request, 'Este acesso já está vinculado a outra lista.')
    else:
        VinculoPainel.objects.create(lista=lista, painel=acesso.painel, painel_id=acesso.painel_id, manual=True)
        messages.success(request, f'{acesso.usuario} vinculado a {lista.cliente.nome} · {lista.nome}.')
    return redirect('conferencia:painel')


@login_required
@require_POST
def desvincular(request, pk):
    VinculoPainel.objects.filter(pk=pk).delete()
    messages.success(request, 'Vínculo removido.')
    return redirect('conferencia:painel')


@login_required
@require_POST
def ignorar(request):
    chave = request.POST.get('chave', '').strip()
    if chave:
        DivergenciaIgnorada.objects.get_or_create(
            chave=chave, defaults={'descricao': request.POST.get('descricao', '')[:300]},
        )
    return redirect('conferencia:painel')


@login_required
@require_POST
def restaurar(request, pk):
    DivergenciaIgnorada.objects.filter(pk=pk).delete()
    return redirect('conferencia:painel')
