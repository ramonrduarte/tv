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

    class Meta:
        verbose_name = 'Leitura de painel'
        verbose_name_plural = 'Leituras de painéis'
        ordering = ['-lida_em']

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
