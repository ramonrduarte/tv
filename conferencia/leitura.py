import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from listas.models import ListaCanais

from .models import AcessoPainel, ConfiguracaoConferencia, LeituraPainel, VinculoPainel

KNEWCMS_API = 'https://mcapi.knewcms.com:2087'
BIT_API = 'https://public-api.bitpanel.vip/v1'
# Uma leitura muito menor que a anterior costuma ser filtro ou falha, não clientes que sumiram.
PROPORCAO_MINIMA = 0.5


class LeituraInvalida(Exception):
    """A leitura não é confiável e os dados anteriores devem ser mantidos."""


def assinar_senha(senha):
    """Permite comparar a senha do painel com a do sistema sem guardá-la."""
    if not senha:
        return ''
    return hmac.new(settings.SECRET_KEY.encode(), senha.encode(), hashlib.sha256).hexdigest()


def painel_do_servidor(servidor):
    """Liga o nome do servidor ao painel. Servidor desconhecido não é conferido por ausência."""
    if not servidor:
        return None
    nome = servidor.nome.strip().lower()
    if nome.startswith('bit'):
        return 'bit'
    if nome.startswith(('warez', 'knew', 'ww')):
        return 'knewcms'
    return ''


def vincular_automaticamente(painel):
    """Vincula só quando o login é igual e aponta para uma única lista possível."""
    ja_vinculadas = set(VinculoPainel.objects.values_list('lista_id', flat=True))
    ids_usados = set(VinculoPainel.objects.filter(painel=painel).values_list('painel_id', flat=True))
    por_login = defaultdict(list)
    for lista in ListaCanais.objects.select_related('servidor'):
        if painel_do_servidor(lista.servidor) in (painel, None):
            por_login[lista.usuario.strip().lower()].append(lista)

    for acesso in AcessoPainel.objects.filter(painel=painel).exclude(painel_id=''):
        candidatas = por_login.get(acesso.usuario.strip().lower(), [])
        if len(candidatas) != 1 or acesso.painel_id in ids_usados or candidatas[0].pk in ja_vinculadas:
            continue
        VinculoPainel.objects.create(lista=candidatas[0], painel=painel, painel_id=acesso.painel_id)
        ids_usados.add(acesso.painel_id)
        ja_vinculadas.add(candidatas[0].pk)


def registrar_falha(painel, erro):
    LeituraPainel.objects.create(painel=painel, sucesso=False, erro=str(erro)[:300])


def salvar_leitura(painel, acessos):
    """Substitui a foto do painel. Cada acesso já vem com os campos de AcessoPainel."""
    anterior = LeituraPainel.objects.filter(painel=painel, sucesso=True).first()
    if not acessos:
        raise LeituraInvalida('O painel não retornou nenhum acesso.')
    if anterior and len(acessos) < anterior.total * PROPORCAO_MINIMA:
        raise LeituraInvalida(
            f'A leitura trouxe {len(acessos)} acessos, e a anterior tinha {anterior.total}. '
            'Confira se há filtro aplicado no painel.'
        )

    with transaction.atomic():
        usuarios = []
        for dados in acessos:
            dados = dict(dados)
            usuario = dados.pop('usuario')
            usuarios.append(usuario)
            AcessoPainel.objects.update_or_create(painel=painel, usuario=usuario, defaults=dados)
        AcessoPainel.objects.filter(painel=painel).exclude(usuario__in=usuarios).delete()
        vincular_automaticamente(painel)
        leitura = LeituraPainel.objects.create(painel=painel, total=len(acessos))
    return leitura


# ---------------------------------------------------------------------------
# knewcms (API, somente GET)
# ---------------------------------------------------------------------------

def _knewcms_get(params):
    url = f'{KNEWCMS_API}/lines?{urllib.parse.urlencode(params)}'
    pedido = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {settings.WWPANEL_API_TOKEN}',
        'Accept': 'application/json',
        'User-Agent': 'IPTV-Manager/1.0',
    })
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            return json.loads(resposta.read().decode())
    except urllib.error.HTTPError as e:
        raise LeituraInvalida(f'A API do knewcms respondeu com erro {e.code}.')
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LeituraInvalida(f'Não foi possível acessar a API do knewcms: {e}')
    except ValueError:
        raise LeituraInvalida('A API do knewcms retornou uma resposta inesperada.')


def _data_knewcms(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace('Z', '+00:00'))
    except ValueError:
        return None


def _acesso_knewcms(item):
    return {
        'usuario': str(item['username']),
        'painel_id': str(item.get('id') or ''),
        'senha_hash': assinar_senha(item.get('password') or ''),
        'ativo': item.get('status') == 1,
        'lixeira': bool(item.get('trash')),
        'teste': bool(item.get('is_trial')),
        'validade': _data_knewcms(item.get('exp_date')),
        'telas': item.get('max_connections'),
        'whatsapp': item.get('whatsapp') or '',
        'observacao': item.get('notes') or '',
    }


def buscar_knewcms():
    """A API separa testes e lixeira por filtro, então cada combinação é lida à parte."""
    acessos = {}
    for is_trial in (0, 1):
        for trash in (0, 1):
            pagina = 1
            while True:
                dados = _knewcms_get({
                    'page': pagina, 'quantityPerPage': 100,
                    'is_trial': is_trial, 'trash': trash,
                })
                try:
                    itens = dados['items']
                    paginas = dados['pagesQuantity']
                    for item in itens:
                        acesso = _acesso_knewcms(item)
                        # O filtro é a fonte confiável caso o campo não venha no item.
                        acesso['lixeira'] = bool(trash)
                        acesso['teste'] = bool(is_trial)
                        acessos[acesso['usuario']] = acesso
                except (KeyError, TypeError):
                    raise LeituraInvalida('A API do knewcms retornou um formato inesperado.')
                if pagina >= paginas:
                    break
                pagina += 1
    return list(acessos.values())


# ---------------------------------------------------------------------------
# BIT (API do revendedor, somente GET; identifica os acessos só pelo usuário)
# ---------------------------------------------------------------------------

def _bit_get(caminho, params):
    url = f'{BIT_API}{caminho}?{urllib.parse.urlencode(params)}'
    pedido = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {settings.BIT_API_TOKEN}',
        'Accept': 'application/json',
        'User-Agent': 'IPTV-Manager/1.0',
    })
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            return json.loads(resposta.read().decode())
    except urllib.error.HTTPError as e:
        # A API devolve {"error": {"code", "message"}}; o código ajuda a saber se é IP ou token.
        try:
            erro = json.loads(e.read().decode()).get('error') or {}
            detalhe = f": {erro.get('code', '')} {erro.get('message', '')}".rstrip()[:160]
        except (ValueError, AttributeError):
            detalhe = ''
        raise LeituraInvalida(f'A API do BIT respondeu com erro {e.code}{detalhe}.')
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LeituraInvalida(f'Não foi possível acessar a API do BIT: {e}')
    except ValueError:
        raise LeituraInvalida('A API do BIT retornou uma resposta inesperada.')


def _acesso_bit(item, teste):
    usuario = str(item.get('username') or '').strip()
    if not usuario:
        raise LeituraInvalida('A API do BIT retornou um acesso sem usuário.')
    return {
        'usuario': usuario,
        'painel_id': '',
        'senha_hash': assinar_senha(item.get('password') or ''),
        # Os testes não trazem status: estão liberados até vencer.
        'ativo': teste or item.get('status') == 'ACTIVE',
        'lixeira': False,
        'teste': teste,
        'validade': _data_knewcms(item.get('expiresAt')),
        'telas': item.get('screens'),
        'whatsapp': str(item.get('whatsapp') or '')[:40],
        'observacao': item.get('notes') or '',
    }


def buscar_bit():
    acessos = {}
    for caminho, teste in (('/lines', False), ('/trials', True)):
        pagina = 1
        while True:
            dados = _bit_get(caminho, {'page': pagina, 'limit': 50})
            try:
                for item in dados['data']:
                    acesso = _acesso_bit(item, teste)
                    acessos[acesso['usuario']] = acesso
                paginas = dados['pagination']['pages']
            except (KeyError, TypeError):
                raise LeituraInvalida('A API do BIT retornou um formato inesperado.')
            if pagina >= paginas:
                break
            pagina += 1
    return list(acessos.values())


# ---------------------------------------------------------------------------
# Leitura dos painéis
# ---------------------------------------------------------------------------

PAINEIS_API = {
    'knewcms': ('WWPANEL_API_TOKEN', buscar_knewcms),
    'bit': ('BIT_API_TOKEN', buscar_bit),
}


def tem_token(painel):
    return bool(getattr(settings, PAINEIS_API[painel][0], ''))


def na_hora(painel):
    """A verificação roda de hora em hora; a folga evita perder o horário por poucos minutos."""
    horas = ConfiguracaoConferencia.atual().intervalo_horas
    if not horas:
        return False
    ultima = LeituraPainel.objects.filter(painel=painel, sucesso=True).first()
    if not ultima:
        return True
    return timezone.now() - ultima.lida_em >= timedelta(hours=horas) - timedelta(minutes=10)


def ler_painel(painel):
    variavel, buscar = PAINEIS_API[painel]
    nome = dict(AcessoPainel.PAINEL_CHOICES)[painel]
    if not tem_token(painel):
        raise LeituraInvalida(f'Chave da API do {nome} não configurada ({variavel}).')
    try:
        return salvar_leitura(painel, buscar())
    except LeituraInvalida as e:
        registrar_falha(painel, e)
        raise
