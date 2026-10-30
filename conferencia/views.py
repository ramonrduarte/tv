import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .bookmarklet import gerar_bookmarklet
from .leitura import CHAVE_CACHE_CONTAGEM, LeituraInvalida, importar_bit, ler_knewcms
from .models import ConfiguracaoConferencia, DivergenciaIgnorada, LeituraPainel
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
def ignorar(request):
    chave = request.POST.get('chave', '').strip()
    if chave:
        DivergenciaIgnorada.objects.get_or_create(
            chave=chave, defaults={'descricao': request.POST.get('descricao', '')[:300]},
        )
        cache.delete(CHAVE_CACHE_CONTAGEM)
    return redirect('conferencia:painel')


@login_required
@require_POST
def restaurar(request, pk):
    DivergenciaIgnorada.objects.filter(pk=pk).delete()
    cache.delete(CHAVE_CACHE_CONTAGEM)
    return redirect('conferencia:painel')
