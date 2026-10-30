import difflib
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

from django.core.cache import cache
from django.utils import timezone

from listas.models import ListaCanais

from .leitura import CHAVE_CACHE_CONTAGEM, assinar_senha
from .models import AcessoPainel, DivergenciaIgnorada, LeituraPainel

NOMES_PAINEL = dict(AcessoPainel.PAINEL_CHOICES)

GRUPOS = [
    ('fora_paineis', 'Ativas no sistema, fora dos painéis', 'Podem ter sido excluídas ou estar com o login errado.', 'red'),
    ('lixeira', 'Na lixeira do painel', 'O acesso foi excluído, mas a lista continua ativa no sistema.', 'red'),
    ('vencida', 'Vencidas no painel', 'A lista está ativa no sistema, mas o acesso já venceu.', 'yellow'),
    ('dados', 'Dados diferentes', 'Senha, telas, situação, teste, servidor ou WhatsApp não batem.', 'blue'),
    ('inativa', 'Inativas no sistema, ativas no painel', 'O acesso continua liberado no painel.', 'yellow'),
    ('repetido', 'Login repetido', 'O mesmo login aparece em mais de uma lista ativa.', 'blue'),
    ('fora_sistema', 'Nos painéis, fora do sistema', 'Acessos no painel sem nenhuma lista cadastrada.', 'yellow'),
]


@dataclass
class Divergencia:
    grupo: str
    tipo: str
    titulo: str
    detalhe: str
    usuario: str
    painel: str = ''
    lista_id: int = None
    chave_extra: str = ''

    @property
    def chave(self):
        return f'{self.tipo}|{self.painel}|{self.usuario.lower()}|{self.lista_id or ""}|{self.chave_extra}'[:300]

    @property
    def descricao(self):
        return f'{self.titulo}: {self.detalhe}'[:300]


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


def _digitos(valor):
    return ''.join(c for c in valor or '' if c.isdigit())


def _sem_acento(valor):
    return ''.join(
        c for c in unicodedata.normalize('NFD', (valor or '').lower())
        if unicodedata.category(c) != 'Mn'
    )


def _titulo(lista):
    return f'{lista.cliente.nome} · {lista.nome}'


def _apps(lista):
    return ', '.join(a.app.nome for a in lista.apps.all())


def _comparar_dados(lista, acesso, painel):
    """Diferenças de um acesso válido e ainda fora da lixeira."""
    achados = []
    nome_painel = NOMES_PAINEL[acesso.painel]
    base = f'{acesso.usuario} · {nome_painel}'

    def achar(tipo, detalhe, chave_extra=''):
        achados.append(Divergencia(
            'dados', tipo, _titulo(lista), f'{base} · {detalhe}',
            acesso.usuario, acesso.painel, lista.pk, chave_extra,
        ))

    if painel and painel != acesso.painel:
        achar('servidor', f'O sistema indica {lista.servidor.nome}, mas o acesso está neste painel.')
    if not acesso.ativo:
        achar('bloqueada', 'Bloqueada no painel, ativa no sistema.')
    if acesso.senha_hash and acesso.senha_hash != assinar_senha(lista.senha):
        apps = _apps(lista)
        complemento = f' Se trocar, revise também: {apps}.' if apps else ''
        achar('senha', f'A senha do painel é diferente da salva.{complemento}', acesso.senha_hash[:12])
    if acesso.telas and acesso.telas != lista.num_telas:
        achar('telas', f'{acesso.telas} tela(s) no painel, {lista.num_telas} no sistema.', str(acesso.telas))
    if acesso.painel == 'knewcms' and acesso.teste != lista.em_teste:
        achar('teste', 'Em teste no painel, normal no sistema.' if acesso.teste else 'Normal no painel, em teste no sistema.')
    fone_painel, fone_cliente = _digitos(acesso.whatsapp), _digitos(lista.cliente.whatsapp)
    if fone_painel and fone_cliente and not (fone_painel.endswith(fone_cliente) or fone_cliente.endswith(fone_painel)):
        achar('whatsapp', f'WhatsApp no painel: {acesso.whatsapp} · no sistema: {lista.cliente.whatsapp}.', fone_painel)
    return achados


def _sugestao(acesso, candidatas):
    """Sugere a lista provável pela observação do painel, sem vincular nada."""
    referencia = _sem_acento(acesso.observacao)
    if not referencia:
        return None
    melhor, nota = None, 0.7
    for lista in candidatas:
        atual = difflib.SequenceMatcher(None, referencia, _sem_acento(lista.cliente.nome)).ratio()
        if atual > nota:
            melhor, nota = lista, atual
    return melhor


def calcular_divergencias():
    agora = timezone.now()
    lidos = set(LeituraPainel.objects.filter(sucesso=True).values_list('painel', flat=True))
    acessos = defaultdict(dict)
    for acesso in AcessoPainel.objects.all():
        acessos[acesso.usuario.strip().lower()][acesso.painel] = acesso

    listas = list(
        ListaCanais.objects.select_related('cliente', 'servidor')
        .prefetch_related('apps__app').order_by('cliente__nome', 'nome')
    )
    achados = []
    usados = set()
    sem_painel = []

    for lista in listas:
        login = lista.usuario.strip().lower()
        painel = painel_do_servidor(lista.servidor)
        encontrados = acessos.get(login, {})
        acesso = encontrados.get(painel) or next(iter(encontrados.values()), None)
        if acesso:
            usados.add((acesso.painel, login))

        if not lista.ativa:
            if acesso and acesso.ativo and not acesso.lixeira and (not acesso.validade or acesso.validade >= agora):
                achados.append(Divergencia(
                    'inativa', 'inativa', _titulo(lista),
                    f'{acesso.usuario} · {NOMES_PAINEL[acesso.painel]}', acesso.usuario, acesso.painel, lista.pk,
                ))
            continue

        if not lista.cliente.ativo:
            achados.append(Divergencia(
                'dados', 'cliente_inativo', _titulo(lista),
                f'{lista.usuario} · Cliente inativo com lista ativa.', lista.usuario, '', lista.pk,
            ))

        if not acesso:
            if painel == '':
                sem_painel.append(lista)
            elif painel in lidos or (painel is None and len(lidos) == len(NOMES_PAINEL)):
                onde = NOMES_PAINEL[painel] if painel else 'sem servidor informado'
                achados.append(Divergencia(
                    'fora_paineis', 'fora_paineis', _titulo(lista),
                    f'{lista.usuario} · {onde} · não encontrado.', lista.usuario, painel or '', lista.pk,
                ))
            continue

        if acesso.lixeira:
            achados.append(Divergencia(
                'lixeira', 'lixeira', _titulo(lista),
                f'{acesso.usuario} · {NOMES_PAINEL[acesso.painel]}', acesso.usuario, acesso.painel, lista.pk,
            ))
            continue

        if acesso.validade and acesso.validade < agora:
            pagamento = lista.status_pagamento_display()[0]
            vencida = timezone.localtime(acesso.validade)
            achados.append(Divergencia(
                'vencida', 'vencida', _titulo(lista),
                f'{acesso.usuario} · {NOMES_PAINEL[acesso.painel]} · venceu em {vencida:%d/%m/%Y} · pagamento: {pagamento}.',
                acesso.usuario, acesso.painel, lista.pk, f'{vencida:%Y%m%d}',
            ))
        achados.extend(_comparar_dados(lista, acesso, painel))

    repetidos = Counter(
        (painel_do_servidor(l.servidor), l.usuario.strip().lower()) for l in listas if l.ativa
    )
    for (painel, login), vezes in repetidos.items():
        if vezes > 1:
            nomes = [_titulo(l) for l in listas if l.ativa and l.usuario.strip().lower() == login and painel_do_servidor(l.servidor) == painel]
            achados.append(Divergencia('repetido', 'repetido', login, ' e '.join(nomes), login, painel or ''))

    sem_acesso = [l for l in listas if l.ativa and not acessos.get(l.usuario.strip().lower())]
    for login, por_painel in acessos.items():
        for painel, acesso in por_painel.items():
            if (painel, login) in usados or acesso.lixeira:
                continue
            partes = [NOMES_PAINEL[painel]]
            if acesso.observacao:
                partes.append(acesso.observacao[:80])
            if acesso.validade:
                partes.append(f'válido até {timezone.localtime(acesso.validade):%d/%m/%Y}')
            sugestao = _sugestao(acesso, sem_acesso)
            if sugestao:
                partes.append(f'Pode ser: {_titulo(sugestao)} (login {sugestao.usuario})')
            achados.append(Divergencia(
                'fora_sistema', 'fora_sistema', acesso.usuario, ' · '.join(partes), acesso.usuario, painel,
            ))

    return achados, sem_painel


def montar_conferencia():
    achados, sem_painel = calcular_divergencias()
    ignoradas = {i.chave: i for i in DivergenciaIgnorada.objects.all()}
    visiveis = [a for a in achados if a.chave not in ignoradas]
    grupos = []
    for chave, titulo, descricao, cor in GRUPOS:
        itens = [a for a in visiveis if a.grupo == chave]
        grupos.append({'chave': chave, 'titulo': titulo, 'descricao': descricao, 'cor': cor, 'itens': itens})
    ativas = {a.chave for a in achados}
    return {
        'grupos': grupos,
        'total': len(visiveis),
        'sem_painel': sem_painel,
        'ignoradas': [i for chave, i in ignoradas.items() if chave in ativas],
    }


def contar_divergencias():
    """Contagem do menu. Fica em cache para não recalcular a cada página aberta."""
    total = cache.get(CHAVE_CACHE_CONTAGEM)
    if total is None:
        total = montar_conferencia()['total']
        cache.set(CHAVE_CACHE_CONTAGEM, total, 300)
    return total
