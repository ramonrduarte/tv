from rest_framework import serializers
from clientes.models import Cliente, Pagador
from listas.models import ListaCanais, ListaApp, AppIPTV
from financeiro.models import Mensalidade


class AppIPTVSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppIPTV
        fields = ['id', 'nome']


class ListaAppSerializer(serializers.ModelSerializer):
    app_nome = serializers.CharField(source='app.nome', read_only=True)

    class Meta:
        model = ListaApp
        fields = ['id', 'app_nome', 'usuario_app', 'device_id']


class ListaCanaisResumoSerializer(serializers.ModelSerializer):
    status_pagamento = serializers.SerializerMethodField()
    dns = serializers.SerializerMethodField()
    data_vencimento = serializers.SerializerMethodField()

    class Meta:
        model = ListaCanais
        fields = ['id', 'nome', 'usuario', 'num_telas', 'dns', 'valor_mensalidade',
                  'data_ativacao', 'data_vencimento', 'ultima_atualizacao', 'ativa', 'status_pagamento']

    def get_status_pagamento(self, obj):
        return obj.status_pagamento()

    def get_dns(self, obj):
        return obj.dns_efetivo

    def get_data_vencimento(self, obj):
        proxima = obj.proxima_data_vencimento()
        return proxima.isoformat() if proxima else None


class ClienteSerializer(serializers.ModelSerializer):
    listas = ListaCanaisResumoSerializer(many=True, read_only=True)

    class Meta:
        model = Cliente
        fields = ['id', 'nome', 'whatsapp', 'ativo', 'listas']


class MensalidadeSerializer(serializers.ModelSerializer):
    lista_nome = serializers.CharField(source='lista.nome', read_only=True)
    cliente_nome = serializers.CharField(source='lista.cliente.nome', read_only=True)
    pagador_nome = serializers.SerializerMethodField()

    class Meta:
        model = Mensalidade
        fields = ['id', 'lista', 'lista_nome', 'cliente_nome', 'pagador_nome',
                  'valor', 'vencimento', 'data_pagamento', 'status', 'notas']
        read_only_fields = ['id']

    def get_pagador_nome(self, obj):
        if obj.lista.pagador:
            return obj.lista.pagador.nome
        return obj.lista.cliente.nome


class RegistrarPagamentoSerializer(serializers.Serializer):
    lista_id = serializers.IntegerField()
    data_pagamento = serializers.DateField(required=False)
    notas = serializers.CharField(required=False, allow_blank=True)


class PagamentoAvulsoSerializer(serializers.Serializer):
    """Pagamento distribuído por valor — cobre múltiplas listas/meses automaticamente."""
    whatsapp = serializers.CharField(required=False, allow_blank=True,
                                     help_text='WhatsApp do pagador ou cliente')
    nome = serializers.CharField(required=False, allow_blank=True,
                                 help_text='Nome do pagador ou cliente (busca parcial)')
    valor = serializers.DecimalField(max_digits=10, decimal_places=2,
                                     help_text='Valor total enviado (R$)')
    data_pagamento = serializers.DateField(required=False,
                                           help_text='Data do pagamento (padrão: hoje)')
    notas = serializers.CharField(required=False, allow_blank=True,
                                  help_text='Observação (ex: Pix, Transferência)')

    def validate(self, data):
        if not data.get('whatsapp') and not data.get('nome'):
            raise serializers.ValidationError('Informe whatsapp ou nome do pagador.')
        if data.get('valor', 0) <= 0:
            raise serializers.ValidationError('O valor deve ser maior que zero.')
        return data
