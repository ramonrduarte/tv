from datetime import date, timedelta

from django.test import TestCase

from clientes.models import Cliente
from financeiro.models import Mensalidade

from .models import ListaCanais


class StatusPagamentoTests(TestCase):
    def setUp(self):
        cliente = Cliente.objects.create(nome='Carlos', whatsapp='1')
        self.lista = ListaCanais.objects.create(cliente=cliente, nome='Casa', usuario='c', senha='x')

    def mensalidade(self, dias, status):
        Mensalidade.objects.create(lista=self.lista, valor=25, vencimento=date.today() + timedelta(days=dias), status=status)

    def test_em_aberto_antes_do_vencimento_e_em_dia(self):
        self.mensalidade(5, 'pendente')
        self.assertEqual(self.lista.status_pagamento(), 'em_dia')

    def test_vence_hoje_ainda_e_em_dia(self):
        self.mensalidade(0, 'pendente')
        self.assertEqual(self.lista.status_pagamento(), 'em_dia')

    def test_depois_do_vencimento_e_atrasado(self):
        self.mensalidade(-1, 'pendente')
        self.assertEqual(self.lista.status_pagamento(), 'atrasado')

    def test_sem_mensalidade_continua_sem_registro(self):
        self.assertEqual(self.lista.status_pagamento(), 'sem_registro')
