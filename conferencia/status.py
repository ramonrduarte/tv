"""Saldo de créditos do BIT e IP de saída do servidor, para mostrar nas telas."""
import urllib.request

from django.conf import settings
from django.core.cache import cache

from .leitura import LeituraInvalida, tem_token
from .models import LeituraPainel

CHAVE_IP = 'ip_saida_servidor'
CHAVE_CREDITOS = 'creditos_bit'
TEMPO_CACHE = 600


def _consultas_ligadas():
    # Desligado nos testes, para nenhuma tela fazer chamadas de rede.
    return getattr(settings, 'CONSULTAS_NA_TELA', True)


def ip_publico():
    """IP com que o servidor sai para a internet. É ele que o BIT precisa autorizar."""
    ip = cache.get(CHAVE_IP)
    if ip is None and _consultas_ligadas():
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=5) as resposta:
                ip = resposta.read().decode().strip()[:45]
        except (OSError, ValueError):
            ip = ''
        cache.set(CHAVE_IP, ip, TEMPO_CACHE if ip else 60)
    return ip or ''


def creditos_bit():
    if not tem_token('bit'):
        return None
    creditos = cache.get(CHAVE_CREDITOS)
    if creditos is None and _consultas_ligadas():
        from . import escrita
        try:
            creditos = escrita.bit_creditos()
        except LeituraInvalida:
            creditos = None
        if creditos is not None:
            cache.set(CHAVE_CREDITOS, creditos, TEMPO_CACHE)
    return creditos


def atualizar_creditos(creditos):
    """Depois de renovar, o BIT devolve o saldo novo; ele passa a valer na hora."""
    if creditos is not None:
        cache.set(CHAVE_CREDITOS, creditos, TEMPO_CACHE)


def situacao_bit():
    leituras = LeituraPainel.objects.filter(painel='bit')
    ultima = leituras.first()
    ultima_ok = leituras.filter(sucesso=True).first()
    ip = ip_publico()
    ip_autorizado = ultima_ok.ip_saida if ultima_ok else ''
    falhou = bool(ultima and not ultima.sucesso)
    erro = (ultima.erro if falhou else '').upper()
    recusa_ip = falhou and ('IP' in erro or ' 403' in erro)
    ip_mudou = bool(ip and ip_autorizado and ip != ip_autorizado)
    return {
        'tem_token': tem_token('bit'),
        'creditos': creditos_bit(),
        'ip': ip,
        'ip_autorizado': ip_autorizado,
        'ip_mudou': ip_mudou,
        'recusa_ip': recusa_ip,
        'atencao': ip_mudou or recusa_ip,
        'ok': bool(ultima_ok) and not falhou,
    }
