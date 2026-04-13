from django.db import models
from django.utils import timezone


class Mensalidade(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago'),
        ('atrasado', 'Atrasado'),
        ('cancelado', 'Cancelado'),
    ]

    lista = models.ForeignKey(
        'listas.ListaCanais', on_delete=models.CASCADE,
        related_name='mensalidades', verbose_name='Lista de Canais'
    )
    valor = models.DecimalField('Valor (R$)', max_digits=10, decimal_places=2)
    vencimento = models.DateField('Vencimento')
    data_pagamento = models.DateField('Data do Pagamento', null=True, blank=True)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='pendente')
    referencia = models.CharField('Referência', max_length=7, blank=True, help_text='Formato: YYYY-MM')
    notas = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mensalidade'
        verbose_name_plural = 'Mensalidades'
        ordering = ['-vencimento']

    def __str__(self):
        return f'{self.lista.nome} — {self.referencia} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.referencia:
            self.referencia = self.vencimento.strftime('%Y-%m')
        # Auto-marca como atrasado se venceu sem pagamento
        if self.status == 'pendente' and self.vencimento < timezone.now().date():
            self.status = 'atrasado'
        super().save(*args, **kwargs)

    @property
    def status_cor(self):
        mapa = {
            'pago': 'green',
            'pendente': 'yellow',
            'atrasado': 'red',
            'cancelado': 'gray',
        }
        return mapa.get(self.status, 'gray')
