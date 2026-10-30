"""Agrupa mensalidades e listas por quem paga, sem alterar nenhum dado."""
from collections import OrderedDict

ORDEM_STATUS = {'atrasado': 0, 'pendente': 1, 'sem_registro': 2, 'em_dia': 3}


def responsavel_do_pagamento(lista):
    """Quem paga a lista: o pagador informado ou, sem ele, o próprio cliente."""
    return lista.pagador.nome if lista.pagador_id else lista.cliente.nome


def _chave(nome):
    # A mesma pessoa pode estar cadastrada como cliente e como pagador.
    return nome.strip().lower()


def agrupar_cobrancas(mensalidades):
    """Junta as mensalidades de um mesmo responsável, com o mais antigo primeiro."""
    grupos = OrderedDict()
    for m in sorted(mensalidades, key=lambda x: x.vencimento):
        nome = responsavel_do_pagamento(m.lista)
        grupo = grupos.setdefault(_chave(nome), {
            'nome': nome, 'whatsapp': '', 'tratamento': '', 'itens': [], 'total': 0, 'clientes': set(),
        })
        grupo['itens'].append(m)
        grupo['total'] += m.valor
        grupo['clientes'].add(m.lista.cliente_id)
        if m.lista.pagador_id:
            grupo['whatsapp'] = grupo['whatsapp'] or m.lista.pagador.whatsapp
            grupo['tratamento'] = grupo['tratamento'] or m.lista.pagador.nome.split()[0]
        else:
            grupo['whatsapp'] = grupo['whatsapp'] or m.lista.cliente.whatsapp
            grupo['tratamento'] = grupo['tratamento'] or m.lista.cliente.nome_tratamento

    resultado = list(grupos.values())
    for grupo in resultado:
        grupo['qtd_clientes'] = len(grupo.pop('clientes'))
        grupo['desde'] = grupo['itens'][0].vencimento
        grupo['nomes_listas'] = ', '.join(dict.fromkeys(m.lista.nome for m in grupo['itens']))
    return resultado


def resumir_lista(lista):
    """Dados de uma lista para os cartões da tela de clientes."""
    status, cor = lista.status_pagamento_display()
    chave = lista.status_pagamento()
    if not lista.ativa:
        status, cor, chave = 'Inativa', 'gray', 'inativa'
    elif lista.em_teste:
        status, cor, chave = 'Em teste', 'blue', 'teste'
    abertas = [m for m in lista.mensalidades.all() if m.status in ('pendente', 'atrasado')]
    abertas.sort(key=lambda m: m.vencimento)
    return {
        'lista': lista,
        'status': status,
        'cor': cor,
        'chave': chave,
        'responsavel': responsavel_do_pagamento(lista),
        'paga_propria': not lista.pagador_id or _chave(lista.pagador.nome) == _chave(lista.cliente.nome),
        'aberta': abertas[0] if abertas else None,
        'apps': list(lista.apps.all()),
    }


def _pior_status(itens):
    ativos = [i for i in itens if i['chave'] in ORDEM_STATUS]
    if not ativos:
        return itens[0] if itens else None
    return min(ativos, key=lambda i: ORDEM_STATUS[i['chave']])


def _servidores(itens):
    nomes = dict.fromkeys(i['lista'].servidor.nome for i in itens if i['lista'].servidor_id)
    return ' e '.join(nomes)


def _passa_filtro(item, filtro):
    return filtro == 'todos' or item['chave'] == filtro


def agrupar_por_cliente(clientes, filtro='todos'):
    grupos = []
    for cliente in clientes:
        todos = [resumir_lista(l) for l in cliente.listas.all()]
        itens = [i for i in todos if _passa_filtro(i, filtro)]
        if not itens and (todos or filtro != 'todos'):
            continue
        pior = _pior_status(itens)
        grupos.append({
            'cliente': cliente,
            'nome': cliente.nome,
            'itens': itens,
            'status': pior['status'] if pior else 'Sem lista',
            'cor': pior['cor'] if pior else 'gray',
            'servidores': _servidores(itens),
        })
    return grupos


def agrupar_por_pagador(clientes, filtro='todos'):
    grupos = OrderedDict()
    for cliente in clientes:
        for lista in cliente.listas.all():
            item = resumir_lista(lista)
            if not _passa_filtro(item, filtro):
                continue
            nome = item['responsavel']
            grupos.setdefault(_chave(nome), {'nome': nome, 'itens': []})['itens'].append(item)

    resultado = sorted(grupos.values(), key=lambda g: g['nome'].lower())
    for grupo in resultado:
        pior = _pior_status(grupo['itens'])
        grupo['status'] = pior['status']
        grupo['cor'] = pior['cor']
        grupo['servidores'] = _servidores(grupo['itens'])
        grupo['qtd_clientes'] = len({i['lista'].cliente_id for i in grupo['itens']})
    return resultado
