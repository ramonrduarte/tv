import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from listas.models import ListaCanais

from .bookmarklet import gerar_bookmarklet
from .leitura import LeituraInvalida, importar_bit, ler_knewcms
from .models import AcessoPainel, ConfiguracaoConferencia, DivergenciaIgnorada, LeituraPainel, VinculoPainel
from .regras import montar_conferencia


def _ultima_leitura(painel):
    leituras = LeituraPainel.objects.filter(painel=painel)
    return {
        'sucesso': leituras.filter(sucesso=True).first(),
        'ultima': leituras.first(),
    }


@login_required
def painel(request):
    contexto = montar_conferencia()
    contexto.update({
        'knewcms': _ultima_leitura('knewcms'),
        'bit': _ultima_leitura('bit'),
        'tem_token': bool(settings.WWPANEL_API_TOKEN),
        'configuracao': ConfiguracaoConferencia.atual(),
        'intervalos': ConfiguracaoConferencia.INTERVALO_CHOICES,
        'bookmarklet': gerar_bookmarklet(f'{request.scheme}://{request.get_host()}'),
    })
    return render(request, 'conferencia/painel.html', contexto)


@login_required
@require_POST
def atualizar_knewcms(request):
    try:
        leitura = ler_knewcms()
        messages.success(request, f'knewcms lido: {leitura.total} acessos.')
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
        messages.success(request, f'Leitura do knewcms: {configuracao.get_intervalo_horas_display().lower()}.')
    else:
        messages.error(request, 'Frequência inválida.')
    return redirect('conferencia:painel')


@login_required
def receber_bit(request):
    resposta = render(request, 'conferencia/receber_bit.html')
    # O padrão do Django (same-origin) separa esta aba da aba do BIT e impede a entrega da leitura.
    resposta['Cross-Origin-Opener-Policy'] = 'unsafe-none'
    return resposta


@login_required
@require_POST
def importar_bit_view(request):
    try:
        dados = json.loads(request.body)
        leitura = importar_bit(dados.get('total'), dados.get('linhas'))
    except (ValueError, AttributeError):
        return JsonResponse({'erro': 'A leitura do BIT veio em um formato inesperado.'}, status=400)
    except LeituraInvalida as e:
        return JsonResponse({'erro': str(e)}, status=400)
    return JsonResponse({'total': leitura.total})


@login_required
@require_POST
def vincular(request):
    """Só registra o vínculo: não altera login nem senha da lista."""
    acesso = get_object_or_404(AcessoPainel, pk=request.POST.get('acesso_id') or 0)
    lista = ListaCanais.objects.filter(pk=request.POST.get('lista_id') or 0).first()
    if not lista:
        messages.error(request, 'Escolha a lista para vincular.')
    elif not acesso.painel_id:
        messages.error(request, 'Este acesso ainda não tem identificador. Faça uma nova leitura do painel.')
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
