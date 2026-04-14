import calendar
from datetime import date
from django.db import models
from django.utils import timezone


def add_one_month(dt):
    """Adiciona exatamente 1 mês a uma data, respeitando fim de mês."""
    month = dt.month % 12 + 1
    year = dt.year + (dt.month // 12)
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class Plano(models.Model):
    nome = models.CharField('Nome do Plano', max_length=200)
    preco_por_tela = models.DecimalField('Preço por Tela (R$)', max_digits=10, decimal_places=2,
                                         help_text='Valor cobrado do cliente por cada tela/acesso')
    custo_por_tela = models.DecimalField('Custo por Tela (R$)', max_digits=10, decimal_places=2,
                                          help_text='Seu custo por cada tela/acesso')
    descricao = models.TextField('Descrição', blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plano'
        verbose_name_plural = 'Planos'
        ordering = ['preco_por_tela', 'nome']

    def __str__(self):
        return f'{self.nome} (R$ {self.preco_por_tela}/tela)'

    @property
    def margem_por_tela(self):
        return self.preco_por_tela - self.custo_por_tela

    @property
    def margem_percentual(self):
        if self.preco_por_tela:
            return round((self.margem_por_tela / self.preco_por_tela) * 100, 1)
        return 0


class Servidor(models.Model):
    nome = models.CharField('Nome', max_length=200)
    dns = models.CharField('DNS / URL', max_length=500)
    porta = models.IntegerField('Porta', default=80)
    ativo = models.BooleanField('Ativo', default=True)
    notas = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Servidor'
        verbose_name_plural = 'Servidores'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.dns}:{self.porta})'


class AppIPTV(models.Model):
    nome = models.CharField('Nome do App', max_length=100)
    servidores = models.ManyToManyField(
        Servidor, blank=True,
        related_name='apps', verbose_name='Servidores compatíveis'
    )
    instrucoes = models.TextField(
        'Instruções de Cadastro', blank=True,
        help_text='Modelo de texto para orientar o cliente no cadastro. Disponível para cópia rápida na listagem.'
    )
    notas = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aplicativo'
        verbose_name_plural = 'Aplicativos'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ListaCanais(models.Model):
    cliente = models.ForeignKey(
        'clientes.Cliente', on_delete=models.CASCADE,
        related_name='listas', verbose_name='Cliente'
    )
    pagador = models.ForeignKey(
        'clientes.Pagador', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='listas_pagas', verbose_name='Pagador'
    )
    plano = models.ForeignKey(
        Plano, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='listas', verbose_name='Plano'
    )
    servidor = models.ForeignKey(
        Servidor, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='listas', verbose_name='Servidor'
    )
    nome = models.CharField('Nome da Lista', max_length=200)
    usuario = models.CharField('Usuário', max_length=200)
    senha = models.CharField('Senha', max_length=200)
    num_telas = models.PositiveSmallIntegerField('Qtd. de Telas', default=1)
    dns_customizado = models.CharField(
        'DNS Customizado', max_length=500, blank=True,
        help_text='Preencha apenas se for diferente do servidor'
    )
    aparelho = models.CharField(
        'Aparelho', max_length=200, blank=True,
        help_text='Ex: Fire Stick, Samsung Smart TV, Celular Android'
    )
    valor_mensalidade = models.DecimalField('Valor Mensalidade (R$)', max_digits=10, decimal_places=2, default=0)
    data_ativacao = models.DateField(
        'Data de Ativação', null=True, blank=True,
        help_text='Define o dia de vencimento mensal (ex: ativado dia 10 → vence todo dia 10)'
    )
    ultima_atualizacao = models.DateField('Última Atualização da Lista', null=True, blank=True)
    controle_desde = models.DateField(
        'Controlar a partir de', null=True, blank=True,
        help_text='Preencha ao cadastrar clientes antigos. Mensalidades anteriores a esta data serão ignoradas no status e vencimento.'
    )
    ativa = models.BooleanField('Ativa', default=True)
    em_teste = models.BooleanField('Em Teste', default=False)
    data_inicio_teste = models.DateField('Início do Teste', null=True, blank=True)
    notas = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lista de Canais'
        verbose_name_plural = 'Listas de Canais'
        ordering = ['cliente__nome', 'nome']

    def __str__(self):
        return f'{self.nome} — {self.cliente.nome}'

    @property
    def dns_efetivo(self):
        if self.dns_customizado:
            return self.dns_customizado
        if self.servidor:
            return f'{self.servidor.dns}:{self.servidor.porta}'
        return '—'

    def status_pagamento(self):
        hoje = timezone.now().date()
        qs = self.mensalidades.order_by('-vencimento')
        if self.controle_desde:
            qs = qs.filter(vencimento__gte=self.controle_desde)
        ultima = qs.first()
        if not ultima:
            return 'sem_registro'
        if ultima.status == 'pago':
            return 'em_dia'
        if ultima.vencimento < hoje:
            return 'atrasado'
        return 'pendente'

    def status_pagamento_display(self):
        mapa = {
            'em_dia': ('Em dia', 'green'),
            'atrasado': ('Atrasado', 'red'),
            'pendente': ('Pendente', 'yellow'),
            'sem_registro': ('Sem registro', 'gray'),
        }
        return mapa.get(self.status_pagamento(), ('—', 'gray'))

    def proxima_data_vencimento(self):
        """Calcula a próxima data de vencimento com base na última mensalidade ou data de ativação."""
        qs = self.mensalidades.order_by('-vencimento')
        if self.controle_desde:
            qs = qs.filter(vencimento__gte=self.controle_desde)
        ultima = qs.first()
        if ultima:
            return add_one_month(ultima.vencimento)
        # Nenhuma mensalidade relevante: usa controle_desde ou data_ativacao como ponto de partida
        ref = self.controle_desde or self.data_ativacao
        if ref:
            return ref
        return None

    @property
    def valor_calculado(self):
        """Valor baseado no plano × número de telas."""
        if self.plano:
            return self.plano.preco_por_tela * self.num_telas
        return self.valor_mensalidade

    @property
    def custo_calculado(self):
        """Custo baseado no plano × número de telas."""
        if self.plano:
            return self.plano.custo_por_tela * self.num_telas
        return None

    @property
    def margem_calculada(self):
        if self.custo_calculado is not None:
            return self.valor_mensalidade - self.custo_calculado
        return None

    def apps_disponiveis(self):
        """Retorna apps compatíveis com o servidor desta lista."""
        if self.servidor:
            apps = self.servidor.apps.all()
            if apps.exists():
                return apps
        return AppIPTV.objects.all()


class ListaApp(models.Model):
    lista = models.ForeignKey(ListaCanais, on_delete=models.CASCADE, related_name='apps', verbose_name='Lista')
    app = models.ForeignKey(AppIPTV, on_delete=models.CASCADE, verbose_name='Aplicativo')
    usuario_app = models.CharField('Usuário no App', max_length=200, blank=True)
    senha_app = models.CharField('Senha no App', max_length=200, blank=True)
    device_id = models.CharField('Device ID / MAC', max_length=200, blank=True)
    notas = models.TextField('Observações', blank=True)

    class Meta:
        verbose_name = 'App da Lista'
        verbose_name_plural = 'Apps da Lista'

    def __str__(self):
        return f'{self.app.nome} — {self.lista.nome}'
