from django.db import models


class AcessoPainel(models.Model):
    """Foto de um acesso como ele estava no painel na última leitura. A senha não é guardada."""
    PAINEL_CHOICES = [
        ('bit', 'BIT'),
        ('knewcms', 'knewcms'),
    ]

    painel = models.CharField('Painel', max_length=20, choices=PAINEL_CHOICES)
    usuario = models.CharField('Usuário', max_length=200)
    painel_id = models.CharField('ID no painel', max_length=50, blank=True)
    senha_hash = models.CharField('Assinatura da senha', max_length=64, blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    lixeira = models.BooleanField('Na lixeira', default=False)
    teste = models.BooleanField('Em teste', default=False)
    validade = models.DateTimeField('Validade', null=True, blank=True)
    telas = models.PositiveSmallIntegerField('Telas', null=True, blank=True)
    whatsapp = models.CharField('WhatsApp', max_length=40, blank=True)
    observacao = models.TextField('Observação', blank=True)
    pacote = models.CharField('Pacote no painel', max_length=200, blank=True)
    lido_em = models.DateTimeField('Lido em', auto_now=True)

    class Meta:
        verbose_name = 'Acesso no painel'
        verbose_name_plural = 'Acessos nos painéis'
        ordering = ['painel', 'usuario']
        constraints = [
            models.UniqueConstraint(fields=['painel', 'usuario'], name='conferencia_acesso_unico'),
        ]

    def __str__(self):
        return f'{self.usuario} ({self.get_painel_display()})'


class VinculoPainel(models.Model):
    """Liga a lista ao acesso por um identificador que não muda quando o usuário é trocado."""
    lista = models.OneToOneField(
        'listas.ListaCanais', on_delete=models.CASCADE,
        related_name='vinculo_painel', verbose_name='Lista',
    )
    painel = models.CharField('Painel', max_length=20, choices=AcessoPainel.PAINEL_CHOICES)
    painel_id = models.CharField('ID no painel', max_length=50)
    manual = models.BooleanField('Feito à mão', default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Vínculo com o painel'
        verbose_name_plural = 'Vínculos com os painéis'
        constraints = [
            models.UniqueConstraint(fields=['painel', 'painel_id'], name='conferencia_vinculo_unico'),
        ]

    def __str__(self):
        return f'{self.lista} → {self.get_painel_display()} {self.painel_id}'


class LeituraPainel(models.Model):
    painel = models.CharField('Painel', max_length=20, choices=AcessoPainel.PAINEL_CHOICES)
    lida_em = models.DateTimeField('Lida em', auto_now_add=True)
    sucesso = models.BooleanField('Sucesso', default=True)
    total = models.PositiveIntegerField('Acessos lidos', default=0)
    erro = models.CharField('Erro', max_length=300, blank=True)
    ip_saida = models.CharField('IP de saída do servidor', max_length=45, blank=True)

    class Meta:
        verbose_name = 'Leitura de painel'
        verbose_name_plural = 'Leituras de painéis'
        ordering = ['-lida_em', '-pk']

    def __str__(self):
        return f'{self.get_painel_display()} em {self.lida_em:%d/%m/%Y %H:%M}'


class ConfiguracaoConferencia(models.Model):
    INTERVALO_CHOICES = [
        (0, 'Só manual'),
        (24, '1 vez ao dia'),
        (12, '2 vezes ao dia'),
        (6, '4 vezes ao dia'),
    ]

    intervalo_horas = models.PositiveSmallIntegerField(
        'Leitura automática do knewcms', choices=INTERVALO_CHOICES, default=12,
    )
    plano_bit = models.CharField('Plano do BIT usado na renovação', max_length=60, blank=True)

    class Meta:
        verbose_name = 'Configuração da conferência'
        verbose_name_plural = 'Configuração da conferência'

    def __str__(self):
        return self.get_intervalo_horas_display()

    @classmethod
    def atual(cls):
        return cls.objects.get_or_create(pk=1)[0]


class DivergenciaIgnorada(models.Model):
    chave = models.CharField('Chave', max_length=300, unique=True)
    descricao = models.CharField('Descrição', max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Divergência ignorada'
        verbose_name_plural = 'Divergências ignoradas'
        ordering = ['-criado_em']

    def __str__(self):
        return self.descricao or self.chave


class OperacaoPainel(models.Model):
    """Registro de cada alteração enviada a um painel. Nunca guarda senhas."""
    TIPO_CHOICES = [
        ('renovacao', 'Renovação'),
        ('senha', 'Troca de senha'),
        ('usuario', 'Troca de usuário'),
        ('copia', 'Senha trazida do painel'),
        ('cadastro', 'Alteração no cadastro'),
    ]
    STATUS_CHOICES = [
        ('pendente', 'Enviando'),
        ('ok', 'Concluída'),
        ('falha', 'Recusada pelo painel'),
        ('incerta', 'Sem resposta do painel'),
    ]

    lista = models.ForeignKey(
        'listas.ListaCanais', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='operacoes_painel', verbose_name='Lista',
    )
    painel = models.CharField('Painel', max_length=20, choices=AcessoPainel.PAINEL_CHOICES, blank=True)
    usuario_painel = models.CharField('Usuário no painel', max_length=200)
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES)
    detalhe = models.CharField('Detalhe', max_length=200, blank=True)
    status = models.CharField('Situação', max_length=20, choices=STATUS_CHOICES, default='pendente')
    erro = models.CharField('Erro', max_length=300, blank=True)
    validade_antes = models.DateTimeField('Validade antes', null=True, blank=True)
    validade_depois = models.DateTimeField('Validade depois', null=True, blank=True)
    feito_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Feito por')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Operação no painel'
        verbose_name_plural = 'Operações nos painéis'
        ordering = ['-criado_em', '-pk']

    def __str__(self):
        return f'{self.get_tipo_display()} {self.usuario_painel} ({self.get_status_display()})'


class PlanoRenovacaoLista(models.Model):
    """Plano do BIT usado para renovar cada lista. Cada lista tem o seu, para não misturar custos."""
    lista = models.OneToOneField(
        'listas.ListaCanais', on_delete=models.CASCADE,
        related_name='plano_renovacao', verbose_name='Lista',
    )
    plano_bit = models.CharField('Plano do BIT', max_length=60)
    nome = models.CharField('Nome do plano', max_length=200, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plano de renovação da lista'
        verbose_name_plural = 'Planos de renovação das listas'

    def __str__(self):
        return f'{self.lista} → {self.nome or self.plano_bit}'


class PacoteLista(models.Model):
    """Pacote de TV registrado no cadastro da lista, entre os pacotes do painel do servidor."""
    lista = models.OneToOneField(
        'listas.ListaCanais', on_delete=models.CASCADE,
        related_name='pacote_painel', verbose_name='Lista',
    )
    painel = models.CharField('Painel', max_length=20, choices=AcessoPainel.PAINEL_CHOICES)
    pacote_id = models.CharField('ID do pacote no painel', max_length=60, blank=True)
    nome = models.CharField('Pacote', max_length=200)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pacote da lista'
        verbose_name_plural = 'Pacotes das listas'

    def __str__(self):
        return f'{self.lista} → {self.nome}'
