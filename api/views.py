from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone

from clientes.models import Cliente, Pagador
from listas.models import ListaCanais
from financeiro.models import Mensalidade
from .serializers import (
    ClienteSerializer, ListaCanaisResumoSerializer,
    MensalidadeSerializer, RegistrarPagamentoSerializer,
    PagamentoAvulsoSerializer,
)


class WhatsAppTokenPermission:
    """Valida token fixo para o agente WhatsApp."""
    def has_permission(self, request):
        token = request.headers.get('X-Api-Token', '')
        expected = settings.API_TOKEN_WHATSAPP
        return expected and token == expected


def _normalizar_whatsapp(numero):
    return ''.join(filter(str.isdigit, numero or ''))


def _buscar_pagador(whatsapp=None, nome=None):
    """
    Identifica quem está pagando e retorna suas listas ativas.

    Busca em ordem:
    1. Tabela Pagador (por whatsapp ou nome)
    2. Tabela Cliente (para quem paga as próprias listas)

    Retorna (nome_exibicao, listas_queryset) ou (None, None) se não encontrado.
    """
    if whatsapp:
        numero = _normalizar_whatsapp(whatsapp)
        # Procura no cadastro de Pagadores
        for p in Pagador.objects.all():
            p_num = _normalizar_whatsapp(p.whatsapp)
            if p_num and (p_num == numero or p_num.endswith(numero) or numero.endswith(p_num)):
                listas = ListaCanais.objects.filter(ativa=True, pagador=p)
                return p.nome, listas

        # Procura no cadastro de Clientes (listas sem pagador separado)
        for c in Cliente.objects.filter(ativo=True):
            c_num = _normalizar_whatsapp(c.whatsapp)
            if c_num and (c_num == numero or c_num.endswith(numero) or numero.endswith(c_num)):
                listas = ListaCanais.objects.filter(ativa=True, cliente=c, pagador__isnull=True)
                return c.nome, listas

    if nome:
        nome_q = nome.strip()
        # Tenta exato primeiro (case-insensitive), depois parcial
        p = (Pagador.objects.filter(nome__iexact=nome_q).first()
             or Pagador.objects.filter(nome__icontains=nome_q).first())
        if p:
            listas = ListaCanais.objects.filter(ativa=True, pagador=p)
            return p.nome, listas

        c = (Cliente.objects.filter(nome__iexact=nome_q, ativo=True).first()
             or Cliente.objects.filter(nome__icontains=nome_q, ativo=True).first())
        if c:
            listas = ListaCanais.objects.filter(ativa=True, cliente=c, pagador__isnull=True)
            return c.nome, listas

    return None, None


# ---------------------------------------------------------------------------
# Endpoints existentes
# ---------------------------------------------------------------------------

class ClientePorWhatsAppView(APIView):
    """Busca cliente pelo número de WhatsApp."""
    permission_classes = []

    def get(self, request):
        if not WhatsAppTokenPermission().has_permission(request):
            return Response({'erro': 'Token inválido'}, status=status.HTTP_403_FORBIDDEN)

        whatsapp = request.query_params.get('whatsapp', '').strip()
        if not whatsapp:
            return Response({'erro': 'Parâmetro whatsapp é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

        numero = _normalizar_whatsapp(whatsapp)
        encontrado = None
        for c in Cliente.objects.filter(ativo=True):
            num = _normalizar_whatsapp(c.whatsapp)
            if num and (num == numero or num.endswith(numero) or numero.endswith(num)):
                encontrado = c
                break

        if not encontrado:
            return Response({'erro': 'Cliente não encontrado'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClienteSerializer(encontrado)
        return Response(serializer.data)


class ListasPorWhatsAppView(APIView):
    """Retorna listas ativas de um cliente pelo WhatsApp."""
    permission_classes = []

    def get(self, request):
        if not WhatsAppTokenPermission().has_permission(request):
            return Response({'erro': 'Token inválido'}, status=status.HTTP_403_FORBIDDEN)

        whatsapp = request.query_params.get('whatsapp', '').strip()
        if not whatsapp:
            return Response({'erro': 'Parâmetro whatsapp é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

        numero = _normalizar_whatsapp(whatsapp)
        encontrado = None
        for c in Cliente.objects.filter(ativo=True):
            num = _normalizar_whatsapp(c.whatsapp)
            if num and (num == numero or num.endswith(numero) or numero.endswith(num)):
                encontrado = c
                break

        if not encontrado:
            return Response({'erro': 'Cliente não encontrado'}, status=status.HTTP_404_NOT_FOUND)

        listas = ListaCanais.objects.filter(cliente=encontrado, ativa=True)
        serializer = ListaCanaisResumoSerializer(listas, many=True)
        return Response({
            'cliente': encontrado.nome,
            'whatsapp': encontrado.whatsapp,
            'listas': serializer.data,
        })


class RegistrarPagamentoView(APIView):
    """Registra pagamento de uma mensalidade específica (por lista_id)."""
    permission_classes = []

    def post(self, request):
        if not WhatsAppTokenPermission().has_permission(request):
            return Response({'erro': 'Token inválido'}, status=status.HTTP_403_FORBIDDEN)

        serializer = RegistrarPagamentoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lista_id = serializer.validated_data['lista_id']
        data_pagamento = serializer.validated_data.get('data_pagamento', timezone.now().date())
        notas = serializer.validated_data.get('notas', '')

        try:
            lista = ListaCanais.objects.get(pk=lista_id)
        except ListaCanais.DoesNotExist:
            return Response({'erro': 'Lista não encontrada'}, status=status.HTTP_404_NOT_FOUND)

        mensalidade = (
            Mensalidade.objects
            .filter(lista=lista, status__in=['pendente', 'atrasado'])
            .order_by('vencimento')
            .first()
        )

        if not mensalidade:
            return Response(
                {'erro': 'Nenhuma mensalidade pendente encontrada para esta lista'},
                status=status.HTTP_404_NOT_FOUND
            )

        mensalidade.status = 'pago'
        mensalidade.data_pagamento = data_pagamento
        if notas:
            mensalidade.notas = notas
        mensalidade.save()

        return Response({
            'sucesso': True,
            'mensagem': f'Pagamento de {mensalidade.vencimento} registrado para {lista.cliente.nome}',
            'mensalidade': MensalidadeSerializer(mensalidade).data,
        })


class StatusMensalidadesView(APIView):
    """Retorna status das mensalidades de um cliente."""
    permission_classes = []

    def get(self, request):
        if not WhatsAppTokenPermission().has_permission(request):
            return Response({'erro': 'Token inválido'}, status=status.HTTP_403_FORBIDDEN)

        whatsapp = request.query_params.get('whatsapp', '').strip()
        if not whatsapp:
            return Response({'erro': 'Parâmetro whatsapp é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

        numero = _normalizar_whatsapp(whatsapp)
        encontrado = None
        for c in Cliente.objects.filter(ativo=True):
            num = _normalizar_whatsapp(c.whatsapp)
            if num and (num == numero or num.endswith(numero) or numero.endswith(num)):
                encontrado = c
                break

        if not encontrado:
            return Response({'erro': 'Cliente não encontrado'}, status=status.HTTP_404_NOT_FOUND)

        resultado = []
        for lista in encontrado.listas.filter(ativa=True):
            ultima = lista.mensalidades.order_by('-vencimento').first()
            resultado.append({
                'lista_id': lista.id,
                'lista_nome': lista.nome,
                'status': lista.status_pagamento(),
                'ultima_mensalidade': MensalidadeSerializer(ultima).data if ultima else None,
            })

        return Response({
            'cliente': encontrado.nome,
            'listas': resultado,
        })


# ---------------------------------------------------------------------------
# Novos endpoints — pagamento por valor (múltiplas listas/meses)
# ---------------------------------------------------------------------------

class PendenciasView(APIView):
    """
    Retorna todas as mensalidades pendentes/atrasadas de um pagador.
    Usado pelo agente antes de registrar o pagamento.

    GET /api/pendencias/?whatsapp=5511...
    GET /api/pendencias/?nome=Raquel
    """
    permission_classes = []

    def get(self, request):
        if not WhatsAppTokenPermission().has_permission(request):
            return Response({'erro': 'Token inválido'}, status=status.HTTP_403_FORBIDDEN)

        whatsapp = request.query_params.get('whatsapp', '').strip()
        nome = request.query_params.get('nome', '').strip()

        if not whatsapp and not nome:
            return Response(
                {'erro': 'Informe whatsapp ou nome do pagador'},
                status=status.HTTP_400_BAD_REQUEST
            )

        nome_exibicao, listas = _buscar_pagador(whatsapp=whatsapp or None, nome=nome or None)

        if not nome_exibicao:
            return Response({'erro': 'Pagador não encontrado'}, status=status.HTTP_404_NOT_FOUND)

        mensalidades = (
            Mensalidade.objects
            .filter(lista__in=listas, status__in=['pendente', 'atrasado'])
            .select_related('lista__cliente')
            .order_by('vencimento')
        )

        total_pendente = sum(m.valor for m in mensalidades)

        return Response({
            'pagador': nome_exibicao,
            'total_pendente': str(total_pendente),
            'quantidade': mensalidades.count(),
            'mensalidades': MensalidadeSerializer(mensalidades, many=True).data,
        })


class PagamentoAvulsoView(APIView):
    """
    Registra pagamento por valor, distribuindo automaticamente
    pelas mensalidades mais antigas do pagador.

    Exemplo: pagador envia R$100 → cobre múltiplas listas/meses.
    O valor é aplicado às mensalidades mais antigas primeiro.
    Se sobrar troco (valor > total devido), é informado no retorno.

    POST /api/pagamento-avulso/
    {
      "whatsapp": "5511999999999",   // OU
      "nome": "Raquel",
      "valor": 100.00,
      "data_pagamento": "2026-03-30",  // opcional
      "notas": "Pix recebido"          // opcional
    }
    """
    permission_classes = []

    def post(self, request):
        if not WhatsAppTokenPermission().has_permission(request):
            return Response({'erro': 'Token inválido'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PagamentoAvulsoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        dados = serializer.validated_data
        data_pagamento = dados.get('data_pagamento', timezone.now().date())
        notas = dados.get('notas', '')
        valor_enviado = Decimal(str(dados['valor']))

        nome_exibicao, listas = _buscar_pagador(
            whatsapp=dados.get('whatsapp') or None,
            nome=dados.get('nome') or None,
        )

        if not nome_exibicao:
            return Response({'erro': 'Pagador não encontrado'}, status=status.HTTP_404_NOT_FOUND)

        # Mensalidades pendentes/atrasadas, mais antigas primeiro
        mensalidades_pendentes = list(
            Mensalidade.objects
            .filter(lista__in=listas, status__in=['pendente', 'atrasado'])
            .select_related('lista__cliente')
            .order_by('vencimento')
        )

        if not mensalidades_pendentes:
            return Response({
                'pagador': nome_exibicao,
                'aviso': 'Nenhuma mensalidade pendente encontrada.',
                'valor_enviado': str(valor_enviado),
            }, status=status.HTTP_200_OK)

        # Distribui o valor pelas mensalidades existentes (mais antiga primeiro)
        pagas = []
        saldo = valor_enviado

        for m in mensalidades_pendentes:
            if saldo < m.valor:
                break
            m.status = 'pago'
            m.data_pagamento = data_pagamento
            if notas:
                m.notas = notas
            m.save()
            saldo -= m.valor
            pagas.append(m)

        # Se ainda sobra saldo, gera mensalidades futuras e paga
        if saldo > 0:
            from listas.models import add_one_month

            for lista in listas:
                if not lista.data_ativacao:
                    continue
                while saldo >= lista.valor_mensalidade and lista.valor_mensalidade > 0:
                    # Próximo vencimento desta lista
                    ultima_desta = (
                        Mensalidade.objects
                        .filter(lista=lista)
                        .order_by('-vencimento')
                        .first()
                    )
                    if ultima_desta:
                        proximo_venc = add_one_month(ultima_desta.vencimento)
                    else:
                        proximo_venc = lista.data_ativacao

                    # Evita duplicata
                    if Mensalidade.objects.filter(lista=lista, vencimento=proximo_venc).exists():
                        break

                    nova = Mensalidade.objects.create(
                        lista=lista,
                        valor=lista.valor_mensalidade,
                        vencimento=proximo_venc,
                        referencia=proximo_venc.strftime('%Y-%m'),
                        status='pago',
                        data_pagamento=data_pagamento,
                        notas=notas or '',
                    )
                    saldo -= lista.valor_mensalidade
                    pagas.append(nova)

        # Mensalidades que ainda ficaram pendentes
        ids_pagos = {m.id for m in pagas}
        ainda_pendentes = [m for m in mensalidades_pendentes if m.id not in ids_pagos]

        total_pago = valor_enviado - saldo

        resposta = {
            'pagador': nome_exibicao,
            'valor_enviado': str(valor_enviado),
            'total_pago': str(total_pago),
            'mensalidades_pagas': MensalidadeSerializer(pagas, many=True).data,
        }

        if saldo > 0:
            resposta['troco'] = str(saldo)
            resposta['aviso'] = f'Valor enviado excede o total. Troco: R$ {saldo}'

        if ainda_pendentes:
            total_restante = sum(m.valor for m in ainda_pendentes)
            resposta['pendente_restante'] = str(total_restante)
            resposta['mensalidades_pendentes_restantes'] = MensalidadeSerializer(
                ainda_pendentes, many=True
            ).data

        return Response(resposta, status=status.HTTP_200_OK)
