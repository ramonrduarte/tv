"""Alterações enviadas aos painéis. Cada função faz um único pedido e nunca repete sozinha."""
import urllib.parse

from django.conf import settings

from .leitura import BIT_API, KNEWCMS_API, LeituraInvalida, _chamar, _data_knewcms

MESES_PERMITIDOS = (1, 2, 3, 6, 12)


def _knewcms(metodo, caminho, params=None, corpo=None):
    return _chamar(KNEWCMS_API, settings.WWPANEL_API_TOKEN, 'knewcms', metodo, caminho, params, corpo)


def _bit(metodo, caminho, params=None, corpo=None):
    return _chamar(BIT_API, settings.BIT_API_TOKEN, 'BIT', metodo, caminho, params, corpo)


def _q(valor):
    return urllib.parse.quote(str(valor), safe='')


def bit_planos():
    dados = _bit('GET', '/plans')
    itens = dados.get('data', []) if isinstance(dados, dict) else dados
    planos = []
    for plano in itens or []:
        if isinstance(plano, dict) and plano.get('id'):
            planos.append((str(plano['id']), str(plano.get('title') or plano.get('name') or plano['id'])))
    return planos


def bit_creditos():
    return _bit('GET', '/me').get('credits')


def renovar(acesso, meses, plano_bit=''):
    """Devolve (nova validade, créditos restantes ou None)."""
    if acesso.painel == 'knewcms':
        if not acesso.painel_id:
            raise LeituraInvalida('Acesso do knewcms sem ID. Atualize a leitura do painel.')
        resposta = _knewcms('PATCH', f'/lines/v2/extend/{_q(acesso.painel_id)}', corpo={'months': meses})
        return _data_knewcms(resposta.get('exp_date')), None
    if not plano_bit:
        raise LeituraInvalida('Escolha o plano do BIT para renovar.')
    resposta = _bit('POST', f'/lines/{_q(acesso.usuario)}/renew', corpo={'planId': plano_bit, 'periodInMonths': meses})
    linha = resposta.get('line') or {}
    return _data_knewcms(linha.get('expiresAt')), resposta.get('credits')


def alterar_senha_knewcms(acesso, nova_senha):
    """A API exige WhatsApp e país junto com a senha, então eles são relidos do painel e mantidos."""
    if not acesso.painel_id:
        raise LeituraInvalida('Acesso do knewcms sem ID. Atualize a leitura do painel.')
    busca = _knewcms('GET', '/lines', {'generalSearch': acesso.usuario, 'page': 1, 'quantityPerPage': 50})
    item = next((i for i in busca.get('items', []) if str(i.get('id')) == acesso.painel_id), None)
    if not item:
        raise LeituraInvalida('Acesso não encontrado no knewcms. Atualize a leitura do painel.')
    corpo = {
        'password': nova_senha,
        'whatsapp': item.get('whatsapp') or '',
        'country': item.get('country') or 'Brasil',
    }
    if item.get('notes'):
        corpo['notes'] = item['notes']
    _knewcms('PATCH', f'/lines/{_q(acesso.painel_id)}', corpo=corpo)


def alterar_usuario_bit(usuario, novo_usuario):
    _bit('PATCH', f'/lines/{_q(usuario)}', corpo={'username': novo_usuario})


def nova_senha_bit(usuario):
    """O BIT não aceita senha escolhida: ele sorteia uma e devolve."""
    resposta = _bit('POST', f'/lines/{_q(usuario)}/password')
    senha = resposta.get('password')
    if not senha:
        raise LeituraInvalida('O BIT não devolveu a nova senha. Confira no painel antes de tentar de novo.')
    return senha


def senha_atual(acesso):
    """Lê a senha que está hoje no painel, sem alterar nada lá."""
    if acesso.painel == 'bit':
        senha = _bit('GET', f'/lines/{_q(acesso.usuario)}').get('password')
    else:
        busca = _knewcms('GET', '/lines', {'generalSearch': acesso.usuario, 'page': 1, 'quantityPerPage': 50})
        item = next((i for i in busca.get('items', []) if str(i.get('id')) == acesso.painel_id
                     or (not acesso.painel_id and i.get('username') == acesso.usuario)), None)
        senha = item.get('password') if item else None
    if not senha:
        raise LeituraInvalida('O painel não devolveu a senha deste acesso.')
    return senha


def links_bit(usuario):
    """Servidor, M3U completa e link curto da lista. Só leitura."""
    dados = _bit('GET', f'/lines/{_q(usuario)}/links')
    return {chave: dados.get(chave) or '' for chave in ('server', 'username', 'm3u', 'short')}


def bit_pacotes():
    dados = _bit('GET', '/packages')
    itens = dados.get('data', []) if isinstance(dados, dict) else dados
    return [(str(p['id']), str(p.get('title') or p['id'])) for p in itens or [] if isinstance(p, dict) and p.get('id')]


# O knewcms tem pacotes fixos, listados na documentação da API (ENUM_PLANS).
KNEWCMS_PACOTES = [
    ('2', 'Essencial 2 IPTV + 1 P2P'),
    ('5', 'Premium 1 IPTV + 2 Nexus'),
    ('10', 'Whot'),
    ('11', 'Ultra 1 Krator+'),
]
