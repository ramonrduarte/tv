import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from listas.models import ListaCanais

from . import escrita, operacoes
from .leitura import PAINEIS_API, LeituraInvalida, ler_painel, tem_token
from .models import (
    AcessoPainel, ConfiguracaoConferencia, DivergenciaIgnorada, LeituraPainel, OperacaoPainel, VinculoPainel,
)
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


# ---------------------------------------------------------------------------
# Renovação em lote e alteração de acesso (gastam créditos ou mudam o painel)
# ---------------------------------------------------------------------------

def _meses(request):
    try:
        meses = int(request.POST.get('meses', ''))
    except ValueError:
        return None
    return meses if meses in escrita.MESES_PERMITIDOS else None


def _voltar(request):
    """Página para onde voltar depois da renovação, só dentro do próprio sistema."""
    destino = request.POST.get('voltar') or request.GET.get('voltar') or ''
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return reverse('conferencia:renovar')


@login_required
def renovar(request):
    busca = request.GET.get('q', '').strip()
    painel = request.GET.get('painel', '')
    painel = painel if painel in PAINEIS_API else ''
    filtro = request.GET.get('filtro') or ('todas' if busca else 'vencendo')
    filtro = filtro if filtro in ('todas', 'vencendo') else 'vencendo'
    return render(request, 'conferencia/renovar.html', {
        'filtro': filtro,
        'busca': busca,
        'painel': painel,
        'paineis': [(p, NOMES_PAINEL[p]) for p in PAINEIS_API],
        'itens': operacoes.candidatas(filtro, busca, painel),
        'meses_opcoes': escrita.MESES_PERMITIDOS,
        'historico': OperacaoPainel.objects.select_related('lista__cliente')[:20],
        'limite': operacoes.LIMITE_LOTE,
    })


@login_required
@require_POST
def renovar_conferir(request):
    meses = _meses(request)
    ids = {int(i) for i in request.POST.getlist('lista') if i.isdigit()}
    itens = [i for i in operacoes.candidatas('todas') if i['lista'].pk in ids]
    voltar = _voltar(request)
    if not itens or not meses:
        messages.error(request, 'Marque ao menos uma lista e escolha os meses.')
        return redirect(voltar)
    if len(itens) > operacoes.LIMITE_LOTE:
        messages.error(request, f'Renove no máximo {operacoes.LIMITE_LOTE} listas por vez.')
        return redirect(voltar)

    tem_bit = any(i['acesso'].painel == 'bit' for i in itens)
    planos, creditos, erro_bit = [], None, ''
    if tem_bit and tem_token('bit'):
        try:
            planos = escrita.bit_planos()
            creditos = escrita.bit_creditos()
        except LeituraInvalida as e:
            erro_bit = str(e)
    lote = uuid.uuid4().hex
    request.session['lote_renovacao'] = lote
    return render(request, 'conferencia/renovar_conferir.html', {
        'itens': itens,
        'meses': meses,
        'lote': lote,
        'qtd_knewcms': sum(1 for i in itens if i['acesso'].painel == 'knewcms'),
        'qtd_bit': sum(1 for i in itens if i['acesso'].painel == 'bit'),
        'tem_bit': tem_bit,
        'planos': planos,
        'plano_salvo': ConfiguracaoConferencia.atual().plano_bit,
        'creditos': creditos,
        'erro_bit': erro_bit,
        'voltar': voltar,
    })


@login_required
@require_POST
def renovar_executar(request):
    # O código do lote vale uma vez só: um segundo envio do mesmo formulário não renova de novo.
    lote = request.POST.get('lote', '')
    voltar = _voltar(request)
    if not lote or request.session.pop('lote_renovacao', None) != lote:
        messages.error(request, 'Este lote já foi enviado ou expirou. Confira o histórico antes de renovar de novo.')
        return redirect(voltar)
    meses = _meses(request)
    ids = [int(i) for i in request.POST.getlist('lista') if i.isdigit()][:operacoes.LIMITE_LOTE]
    if not meses or not ids:
        messages.error(request, 'Lote inválido.')
        return redirect(voltar)
    plano = request.POST.get('plano_bit', '').strip()
    if plano:
        configuracao = ConfiguracaoConferencia.atual()
        configuracao.plano_bit = plano
        configuracao.save()
    resultado = operacoes.executar_renovacao(ids, meses, plano, request.user)
    return render(request, 'conferencia/renovar_resultado.html', {'resultado': resultado, 'meses': meses, 'voltar': voltar})


@login_required
def acesso_editar(request, pk):
    lista = get_object_or_404(ListaCanais.objects.select_related('cliente', 'servidor'), pk=pk)
    acesso = operacoes.acessos_das_listas([lista]).get(lista.pk)
    if request.method == 'POST' and acesso:
        novo_usuario = request.POST.get('novo_usuario', '').strip()
        nova_senha = request.POST.get('nova_senha', '').strip()
        gerar_senha = request.POST.get('gerar_senha') == '1'
        erro = ''
        if not request.POST.get('confirmo'):
            erro = 'Marque a confirmação para alterar no painel.'
        elif not tem_token(acesso.painel):
            erro = f'Falta a chave da API ({PAINEIS_API[acesso.painel][0]}).'
        elif acesso.painel == 'bit' and novo_usuario and (len(novo_usuario) < 3 or ' ' in novo_usuario):
            erro = 'O novo usuário precisa ter ao menos 3 caracteres e não pode ter espaços.'
        elif acesso.painel == 'knewcms' and nova_senha and len(nova_senha) < 4:
            erro = 'A nova senha precisa ter ao menos 4 caracteres.'
        elif not (novo_usuario and novo_usuario != acesso.usuario) and not nova_senha and not gerar_senha:
            erro = 'Nada para alterar.'
        if erro:
            messages.error(request, erro)
        else:
            try:
                feito = operacoes.alterar_acesso(
                    lista, acesso, request.user, novo_usuario=novo_usuario,
                    nova_senha=nova_senha, gerar_senha=gerar_senha,
                )
            except LeituraInvalida as e:
                messages.error(request, f'O painel recusou ou não respondeu: {e} Confira o histórico abaixo.')
            else:
                apps = ', '.join(a.app.nome for a in lista.apps.select_related('app'))
                aviso = f' Atualize também nos aplicativos: {apps}.' if apps else ''
                messages.success(request, ' '.join(feito) + aviso)
        destino = _voltar(request)
        return redirect(destino if destino != reverse('conferencia:renovar') else reverse('conferencia:acesso_editar', args=[lista.pk]))
    return render(request, 'conferencia/acesso_editar.html', {
        'lista': lista,
        'acesso': acesso,
        'historico': OperacaoPainel.objects.filter(lista=lista)[:10],
        'sem_token': bool(acesso) and not tem_token(acesso.painel),
    })
