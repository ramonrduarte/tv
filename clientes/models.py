from django.db import models
from django.utils import timezone


class Cliente(models.Model):
    nome = models.CharField('Nome', max_length=200)
    apelido = models.CharField('Apelido / Como chama', max_length=100, blank=True,
                               help_text='Como você chama essa pessoa. Usado nas mensagens do WhatsApp.')
    whatsapp = models.CharField('WhatsApp', max_length=20)
    ativo = models.BooleanField('Ativo', default=True)
    notas = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def nome_tratamento(self):
        """Retorna apelido se cadastrado, senão o primeiro nome."""
        if self.apelido:
            return self.apelido
        return self.nome.split()[0]

    def status_geral(self):
        """Retorna o pior status entre todas as listas ativas do cliente."""
        listas = self.listas.filter(ativa=True)
        if not listas.exists():
            return 'sem_lista'
        statuses = [l.status_pagamento() for l in listas]
        if 'atrasado' in statuses:
            return 'atrasado'
        if 'pendente' in statuses:
            return 'pendente'
        if 'em_dia' in statuses:
            return 'em_dia'
        return 'sem_registro'


class TemplateMensagem(models.Model):
    TIPO_CHOICES = [
        ('atrasado',  'Mensalidade Atrasada'),
        ('vencendo',  'Vencimento Próximo'),
        ('teste',     'Cliente em Teste'),
    ]
    VARIAVEIS = {
        'atrasado': [
            ('{nome}',       'Apelido ou primeiro nome do cliente'),
            ('{valor}',      'Valor da mensalidade'),
            ('{lista}',      'Nome da lista'),
        ],
        'vencendo': [
            ('{nome}',       'Apelido ou primeiro nome do cliente'),
            ('{valor}',      'Valor da mensalidade'),
            ('{vencimento}', 'Data de vencimento (dd/mm/aaaa)'),
            ('{lista}',      'Nome da lista'),
        ],
        'teste': [
            ('{nome}',       'Apelido ou primeiro nome do cliente'),
            ('{lista}',      'Nome da lista'),
            ('{dias}',       'Quantos dias está em teste'),
        ],
    }

    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES, unique=True)
    mensagem = models.TextField('Mensagem')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Template de Mensagem'
        verbose_name_plural = 'Templates de Mensagem'

    def __str__(self):
        return self.get_tipo_display()

    @classmethod
    def get_template(cls, tipo):
        """Retorna o template do banco ou o padrão se não existir."""
        defaults = {
            'atrasado': 'Olá {nome}! Sua mensalidade de R$ {valor} ({lista}) está em atraso. Poderia efetuar o pagamento? Qualquer dúvida estou à disposição! 😊',
            'vencendo':  'Olá {nome}! Sua mensalidade de R$ {valor} ({lista}) vence em {vencimento}. Qualquer dúvida estou à disposição! 😊',
            'teste':     'Olá {nome}! Seu período de teste ({lista}) está chegando ao fim. Gostaria de continuar? 😊',
        }
        obj = cls.objects.filter(tipo=tipo).first()
        return obj.mensagem if obj else defaults[tipo]

    def renderizar(self, **kwargs):
        """Substitui as variáveis da mensagem."""
        msg = self.mensagem
        for k, v in kwargs.items():
            msg = msg.replace('{' + k + '}', str(v))
        return msg


class Pagador(models.Model):
    nome = models.CharField('Nome', max_length=200)
    whatsapp = models.CharField('WhatsApp', max_length=20, blank=True)
    notas = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pagador'
        verbose_name_plural = 'Pagadores'
        ordering = ['nome']

    def __str__(self):
        return self.nome
