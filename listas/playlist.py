"""Monta a playlist de uma lista: M3U, link curto ou o formato que cada aplicativo pede."""
import re
import urllib.parse

VARIAVEIS = [
    ('{servidor}', 'Endereço do servidor com http:// e porta'),
    ('{host}', 'Só o endereço, sem http:// e sem porta'),
    ('{porta}', 'Só a porta'),
    ('{usuario}', 'Usuário da lista (ou o do app, se preenchido)'),
    ('{senha}', 'Senha da lista (ou a do app, se preenchida)'),
    ('{m3u}', 'Link da lista M3U completa'),
    ('{curto}', 'Link curto (só no BIT)'),
]


class PlaylistIndisponivel(Exception):
    pass


def painel_da_lista(lista):
    from conferencia.leitura import painel_do_servidor
    from conferencia.operacoes import acessos_das_listas
    acesso = acessos_das_listas([lista]).get(lista.pk)
    return acesso.painel if acesso else painel_do_servidor(lista.servidor)


def usa_m3u(lista):
    """O knewcms não trabalha com lista M3U."""
    return painel_da_lista(lista) != 'knewcms'


def _servidor(lista, lista_app=None):
    endereco = (lista_app.dns_customizado if lista_app and lista_app.dns_customizado else '') or ''
    if not endereco and lista.servidor_id:
        endereco = f'{lista.servidor.dns}:{lista.servidor.porta}'
    endereco = endereco.strip().rstrip('/')
    if endereco and not re.match(r'^https?://', endereco):
        endereco = f'http://{endereco}'
    return endereco


def _links_do_painel(lista):
    """No BIT os links vêm da API. Sem API, devolve None e a M3U é montada no padrão Xtream."""
    from conferencia import escrita
    from conferencia.leitura import LeituraInvalida, tem_token
    from conferencia.operacoes import acessos_das_listas
    acesso = acessos_das_listas([lista]).get(lista.pk)
    if not acesso or acesso.painel != 'bit' or not tem_token('bit'):
        return None
    try:
        return escrita.links_bit(acesso.usuario)
    except LeituraInvalida as e:
        raise PlaylistIndisponivel(f'Não foi possível ler os links no BIT: {e}')


def dados(lista, lista_app=None, precisa_links=True):
    servidor = _servidor(lista, lista_app)
    usuario = (lista_app.usuario_app if lista_app and lista_app.usuario_app else '') or lista.usuario
    senha = (lista_app.senha_app if lista_app and lista_app.senha_app else '') or lista.senha
    links = _links_do_painel(lista) if precisa_links else None
    if not servidor and links and links.get('server'):
        servidor = links['server'].rstrip('/')
    partes = urllib.parse.urlparse(servidor) if servidor else None
    m3u = (links or {}).get('m3u') or ''
    if not m3u and servidor and usa_m3u(lista):
        m3u = (f'{servidor}/get.php?username={urllib.parse.quote(usuario)}'
               f'&password={urllib.parse.quote(senha)}&type=m3u_plus&output=ts')
    return {
        'servidor': servidor,
        'host': partes.hostname if partes else '',
        'porta': str(partes.port or '') if partes else '',
        'usuario': usuario,
        'senha': senha,
        'm3u': m3u,
        'curto': (links or {}).get('short') or '',
        'origem': 'painel' if links else 'montada',
    }


def gerar(lista, tipo, lista_app=None):
    """tipo: 'm3u', 'curto' ou 'app'. Devolve (texto, origem)."""
    if tipo == 'app':
        modelo = (lista_app.app.formato_lista if lista_app else '').strip()
        if not modelo:
            raise PlaylistIndisponivel('Este aplicativo não tem modelo de lista cadastrado.')
        precisa = '{m3u}' in modelo or '{curto}' in modelo
        if precisa and not usa_m3u(lista):
            raise PlaylistIndisponivel('O modelo deste app usa M3U, que o knewcms não tem.')
        valores = dados(lista, lista_app, precisa_links=precisa)
        texto = modelo
        for chave in ('servidor', 'host', 'porta', 'usuario', 'senha', 'm3u', 'curto'):
            texto = texto.replace('{' + chave + '}', valores[chave])
        return texto, valores['origem']
    valores = dados(lista, lista_app)
    if tipo == 'curto':
        if not valores['curto']:
            raise PlaylistIndisponivel('Link curto só existe para listas do BIT com a API configurada.')
        return valores['curto'], valores['origem']
    if not valores['m3u']:
        if not usa_m3u(lista):
            raise PlaylistIndisponivel('O knewcms não usa lista M3U.')
        raise PlaylistIndisponivel('A lista não tem servidor para montar a M3U.')
    return valores['m3u'], valores['origem']
