import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import AcessoPainel, ConfiguracaoConferencia, LeituraPainel

KNEWCMS_API = 'https://mcapi.knewcms.com:2087'
CHAVE_CACHE_CONTAGEM = 'conferencia_contagem'
# Uma leitura muito menor que a anterior costuma ser filtro ou falha, não clientes que sumiram.
PROPORCAO_MINIMA = 0.5


class LeituraInvalida(Exception):
    """A leitura não é confiável e os dados anteriores devem ser mantidos."""


def assinar_senha(senha):
    """Permite comparar a senha do painel com a do sistema sem guardá-la."""
    if not senha:
        return ''
    return hmac.new(settings.SECRET_KEY.encode(), senha.encode(), hashlib.sha256).hexdigest()


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
        leitura = LeituraPainel.objects.create(painel=painel, total=len(acessos))
    cache.delete(CHAVE_CACHE_CONTAGEM)
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


def knewcms_na_hora():
    """A verificação roda de hora em hora; a folga evita perder o horário por poucos minutos."""
    horas = ConfiguracaoConferencia.atual().intervalo_horas
    if not horas:
        return False
    ultima = LeituraPainel.objects.filter(painel='knewcms', sucesso=True).first()
    if not ultima:
        return True
    return timezone.now() - ultima.lida_em >= timedelta(hours=horas) - timedelta(minutes=10)


def ler_knewcms():
    if not settings.WWPANEL_API_TOKEN:
        raise LeituraInvalida('Chave da API do knewcms não configurada (WWPANEL_API_TOKEN).')
    try:
        return salvar_leitura('knewcms', buscar_knewcms())
    except LeituraInvalida as e:
        registrar_falha('knewcms', e)
        raise


# ---------------------------------------------------------------------------
# BIT (enviado pelo botão salvo no navegador, a partir da tela de listas)
# ---------------------------------------------------------------------------

def _data_bit(valor):
    try:
        return timezone.make_aware(datetime.strptime((valor or '').strip(), '%d/%m/%Y %H:%M'))
    except ValueError:
        return None


def _acesso_bit(linha):
    usuario = str(linha.get('usuario') or '').strip()
    if not usuario:
        raise LeituraInvalida('Uma das linhas do BIT veio sem usuário.')
    telas = str(linha.get('telas') or '').strip()
    return {
        'usuario': usuario,
        'senha_hash': assinar_senha(str(linha.get('senha') or '').strip()),
        'ativo': str(linha.get('estado') or '').strip().lower().startswith('ativ'),
        'validade': _data_bit(linha.get('validade')),
        'telas': int(telas) if telas.isdigit() else None,
    }


def importar_bit(total, linhas):
    try:
        if not isinstance(linhas, list) or not isinstance(total, int):
            raise LeituraInvalida('A leitura do BIT veio em um formato inesperado.')
        if total != len(linhas):
            raise LeituraInvalida(f'O BIT informou {total} acessos, mas chegaram {len(linhas)}.')
        return salvar_leitura('bit', [_acesso_bit(linha) for linha in linhas])
    except LeituraInvalida as e:
        registrar_falha('bit', e)
        raise
