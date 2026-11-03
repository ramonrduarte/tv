"""Renovação em lote e troca de usuário e senha, com registro de cada pedido."""
import unicodedata
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from listas.models import ListaCanais

from . import escrita
from .leitura import PAINEIS_API, LeituraInvalida, SemResposta, assinar_senha, painel_do_servidor, tem_token
from .models import AcessoPainel, OperacaoPainel, VinculoPainel

LIMITE_LOTE = 30  # O BIT aceita 30 alterações por minuto.
JANELA_REPETICAO = timedelta(minutes=15)


def acessos_das_listas(listas):
    """Mesmo critério da conferência: primeiro o vínculo, depois o login no painel do servidor."""
    por_id, por_login = {}, defaultdict(dict)
    for acesso in AcessoPainel.objects.all():
        por_login[acesso.usuario.strip().lower()][acesso.painel] = acesso
        if acesso.painel_id:
            por_id[(acesso.painel, acesso.painel_id)] = acesso
    vinculos = {v.lista_id: v for v in VinculoPainel.objects.all()}
    resultado = {}
    for lista in listas:
        vinculo = vinculos.get(lista.pk)
        acesso = por_id.get((vinculo.painel, vinculo.painel_id)) if vinculo else None
        if not acesso:
            encontrados = por_login.get(lista.usuario.strip().lower(), {})
            acesso = encontrados.get(painel_do_servidor(lista.servidor)) or next(iter(encontrados.values()), None)
        if acesso:
            resultado[lista.pk] = acesso
    return resultado


def _normalizar(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', (texto or '').lower())
        if unicodedata.category(c) != 'Mn'
    )


def _texto_busca(lista, acesso):
    partes = [
        lista.cliente.nome, lista.cliente.apelido, lista.cliente.whatsapp, lista.nome, lista.usuario,
        lista.pagador.nome if lista.pagador_id else '', lista.servidor.nome if lista.servidor_id else '',
        acesso.usuario, acesso.observacao, acesso.get_painel_display(),
    ]
    return _normalizar(' '.join(p for p in partes if p))


def candidatas(filtro='vencendo', busca='', painel='', cliente_id=None):
    """Busca em cliente, apelido, WhatsApp, pagador, lista, login, servidor e observação do painel."""
    agora = timezone.now()
    listas = ListaCanais.objects.filter(ativa=True)
    if cliente_id:
        listas = listas.filter(cliente_id=cliente_id)
    listas = list(listas.select_related('cliente', 'servidor', 'pagador').order_by('cliente__nome', 'nome'))
    acessos = acessos_das_listas(listas)
    termos = _normalizar(busca).split()
    itens = []
    for lista in listas:
        acesso = acessos.get(lista.pk)
        if not acesso or acesso.lixeira:
            continue
        if painel and acesso.painel != painel:
            continue
        if termos:
            texto = _texto_busca(lista, acesso)
            if not all(t in texto for t in termos):
                continue
        dias = (acesso.validade - agora).days if acesso.validade else None
        if filtro == 'vencendo' and dias is not None and dias > 7:
            continue
        itens.append({
            'lista': lista,
            'acesso': acesso,
            'dias': dias,
            'vencida': dias is not None and acesso.validade < agora,
            'sem_token': not tem_token(acesso.painel),
            'pagamento': lista.status_pagamento_display(),
        })
    itens.sort(key=lambda i: (i['dias'] is None, i['dias'] if i['dias'] is not None else 0))
    return itens


def _recente(lista):
    """Renovação concluída, sem resposta ou em andamento nos últimos minutos bloqueia outra."""
    return OperacaoPainel.objects.filter(
        lista=lista, tipo='renovacao', status__in=('ok', 'incerta', 'pendente'),
        criado_em__gte=timezone.now() - JANELA_REPETICAO,
    ).exists()


def executar_renovacao(lista_ids, meses, plano_bit, usuario):
    listas = list(ListaCanais.objects.filter(pk__in=lista_ids, ativa=True).select_related('cliente', 'servidor'))
    acessos = acessos_das_listas(listas)
    resultado = {'itens': [], 'creditos_bit': None}
    for lista in listas:
        acesso = acessos.get(lista.pk)
        item = {'lista': lista, 'acesso': acesso, 'operacao': None, 'motivo': ''}
        resultado['itens'].append(item)
        if not acesso or acesso.lixeira:
            item['motivo'] = 'Acesso não encontrado no painel.'
            continue
        if not tem_token(acesso.painel):
            item['motivo'] = f'Falta a chave da API ({PAINEIS_API[acesso.painel][0]}).'
            continue
        if _recente(lista):
            item['motivo'] = 'Já foi renovada há poucos minutos. Confira a validade antes de renovar de novo.'
            continue
        operacao = OperacaoPainel.objects.create(
            lista=lista, painel=acesso.painel, usuario_painel=acesso.usuario, tipo='renovacao',
            detalhe=f'{meses} mês' if meses == 1 else f'{meses} meses',
            validade_antes=acesso.validade, feito_por=usuario,
        )
        item['operacao'] = operacao
        try:
            validade, creditos = escrita.renovar(acesso, meses, plano_bit)
        except SemResposta as e:
            operacao.status, operacao.erro = 'incerta', str(e)[:300]
        except LeituraInvalida as e:
            operacao.status, operacao.erro = 'falha', str(e)[:300]
        else:
            operacao.status, operacao.validade_depois = 'ok', validade
            if validade:
                AcessoPainel.objects.filter(pk=acesso.pk).update(validade=validade)
            if creditos is not None:
                resultado['creditos_bit'] = creditos
        operacao.save()
    return resultado


def _registrar(lista, acesso, tipo, detalhe, usuario):
    return OperacaoPainel.objects.create(
        lista=lista, painel=acesso.painel, usuario_painel=acesso.usuario, tipo=tipo, detalhe=detalhe, feito_por=usuario,
    )


def _concluir(operacao, erro=None):
    if isinstance(erro, SemResposta):
        operacao.status = 'incerta'
    elif erro:
        operacao.status = 'falha'
    else:
        operacao.status = 'ok'
    operacao.erro = str(erro or '')[:300]
    operacao.save()


def alterar_acesso(lista, acesso, usuario, novo_usuario='', nova_senha='', gerar_senha=False):
    """Altera no painel e, só depois da confirmação dele, no cadastro da lista. Devolve a lista de mensagens."""
    feito = []
    if acesso.painel == 'bit' and novo_usuario and novo_usuario != acesso.usuario:
        operacao = _registrar(lista, acesso, 'usuario', f'{acesso.usuario} → {novo_usuario}', usuario)
        try:
            escrita.alterar_usuario_bit(acesso.usuario, novo_usuario)
        except LeituraInvalida as e:
            _concluir(operacao, e)
            raise
        _concluir(operacao)
        with transaction.atomic():
            ListaCanais.objects.filter(pk=lista.pk).update(usuario=novo_usuario)
            AcessoPainel.objects.filter(pk=acesso.pk).update(usuario=novo_usuario)
        lista.usuario = acesso.usuario = novo_usuario
        feito.append(f'Usuário alterado para {novo_usuario}.')

    senha = None
    if acesso.painel == 'bit' and gerar_senha:
        operacao = _registrar(lista, acesso, 'senha', 'Senha sorteada pelo BIT', usuario)
        try:
            senha = escrita.nova_senha_bit(acesso.usuario)
        except LeituraInvalida as e:
            _concluir(operacao, e)
            raise
        _concluir(operacao)
    elif acesso.painel == 'knewcms' and nova_senha:
        operacao = _registrar(lista, acesso, 'senha', 'Senha definida no sistema', usuario)
        try:
            escrita.alterar_senha_knewcms(acesso, nova_senha)
        except LeituraInvalida as e:
            _concluir(operacao, e)
            raise
        _concluir(operacao)
        senha = nova_senha

    if senha:
        with transaction.atomic():
            ListaCanais.objects.filter(pk=lista.pk).update(senha=senha)
            AcessoPainel.objects.filter(pk=acesso.pk).update(senha_hash=assinar_senha(senha))
        lista.senha = senha
        feito.append('Senha alterada e salva na lista.')
    return feito


def trazer_senha(lista, acesso, usuario):
    """Copia para a lista a senha que está no painel. Não altera o painel."""
    operacao = _registrar(lista, acesso, 'copia', 'Senha do painel salva na lista', usuario)
    try:
        senha = escrita.senha_atual(acesso)
    except LeituraInvalida as e:
        _concluir(operacao, e)
        raise
    _concluir(operacao)
    with transaction.atomic():
        ListaCanais.objects.filter(pk=lista.pk).update(senha=senha)
        AcessoPainel.objects.filter(pk=acesso.pk).update(senha_hash=assinar_senha(senha))
    lista.senha = senha
