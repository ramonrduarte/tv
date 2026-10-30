from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from financeiro.models import Mensalidade
from listas.models import AppIPTV, ListaApp, ListaCanais, Servidor

from .agrupamento import agrupar_cobrancas, agrupar_por_cliente, agrupar_por_pagador
from .models import Cliente, Pagador


class Base(TestCase):
    def setUp(self):
        self.bit = Servidor.objects.create(nome='Bit', dns='bit.test')
        self.warez = Servidor.objects.create(nome='Warez', dns='warez.test')
        self.marta_pagadora = Pagador.objects.create(nome='Marta Souza', whatsapp='5551900000009')
        self.marta = Cliente.objects.create(nome='Marta Souza', whatsapp='5551900000001')
        self.ana = Cliente.objects.create(nome='Ana Souza', whatsapp='5551900000002')
        self.carlos = Cliente.objects.create(nome='Carlos Prado', whatsapp='5551900000003')
        self.l_marta = self.lista(self.marta, 'Casa', 'marta', self.bit, Decimal('40'))
        self.l_ana = self.lista(self.ana, 'Sala', 'ana', self.warez, pagador=self.marta_pagadora)
        self.l_casa = self.lista(self.carlos, 'Casa', 'carlos', self.bit)
        self.l_sitio = self.lista(self.carlos, 'Sítio', 'sitio', self.warez)

    def lista(self, cliente, nome, usuario, servidor, valor=Decimal('25'), pagador=None, **extra):
        return ListaCanais.objects.create(
            cliente=cliente, nome=nome, usuario=usuario, senha='x', servidor=servidor,
            valor_mensalidade=valor, pagador=pagador, **extra,
        )

    def mensalidade(self, lista, dias, status='atrasado'):
        return Mensalidade.objects.create(
            lista=lista, valor=lista.valor_mensalidade, vencimento=date.today() + timedelta(days=dias), status=status,
        )

    def clientes(self):
        return Cliente.objects.prefetch_related('listas__servidor', 'listas__pagador', 'listas__apps__app', 'listas__mensalidades').order_by('nome')


class CobrancasTests(Base):
    def test_junta_cliente_e_pagador_de_mesmo_nome_e_soma(self):
        self.mensalidade(self.l_marta, -5)
        self.mensalidade(self.l_ana, -10)
        self.mensalidade(self.l_casa, -2)
        grupos = agrupar_cobrancas(Mensalidade.objects.select_related('lista__cliente', 'lista__pagador'))
        self.assertEqual([g['nome'] for g in grupos][1], 'Carlos Prado')
        marta = grupos[0]
        self.assertEqual(marta['total'], Decimal('65'))
        self.assertEqual(marta['qtd_clientes'], 2)
        self.assertEqual(marta['whatsapp'], '5551900000009')
        self.assertEqual(marta['desde'], date.today() - timedelta(days=10))

    def test_quem_paga_a_propria_lista_usa_o_whatsapp_do_cliente(self):
        self.mensalidade(self.l_casa, -1)
        grupo = agrupar_cobrancas(Mensalidade.objects.select_related('lista__cliente', 'lista__pagador'))[0]
        self.assertEqual(grupo['whatsapp'], self.carlos.whatsapp)


class AgrupamentoTests(Base):
    def test_cliente_com_varias_listas_e_servidores(self):
        grupos = {g['nome']: g for g in agrupar_por_cliente(self.clientes())}
        carlos = grupos['Carlos Prado']
        self.assertEqual(len(carlos['itens']), 2)
        self.assertEqual(carlos['servidores'], 'Bit e Warez')

    def test_por_pagador_junta_listas_de_clientes_diferentes(self):
        grupos = {g['nome']: g for g in agrupar_por_pagador(self.clientes())}
        self.assertEqual(grupos['Marta Souza']['qtd_clientes'], 2)
        self.assertEqual(len(grupos['Marta Souza']['itens']), 2)
        self.assertEqual(len(grupos['Carlos Prado']['itens']), 2)

    def test_filtro_atrasado_mostra_so_a_lista_atrasada(self):
        self.mensalidade(self.l_sitio, -3)
        grupos = agrupar_por_cliente(self.clientes(), 'atrasado')
        self.assertEqual([g['nome'] for g in grupos], ['Carlos Prado'])
        self.assertEqual([i['lista'].nome for i in grupos[0]['itens']], ['Sítio'])
        self.assertEqual(grupos[0]['status'], 'Atrasado')

    def test_cliente_sem_lista_aparece_so_em_todos(self):
        Cliente.objects.create(nome='Zeca', whatsapp='1')
        self.assertIn('Zeca', [g['nome'] for g in agrupar_por_cliente(self.clientes())])
        self.assertNotIn('Zeca', [g['nome'] for g in agrupar_por_cliente(self.clientes(), 'atrasado')])

    def test_lista_inativa_nao_define_o_status_do_cliente(self):
        self.mensalidade(self.l_casa, -3)
        self.l_casa.ativa = False
        self.l_casa.save()
        grupos = {g['nome']: g for g in agrupar_por_cliente(self.clientes())}
        self.assertNotEqual(grupos['Carlos Prado']['status'], 'Atrasado')


class TelasTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_user('ramon', password='x'))

    def test_clientes_mostra_cartoes_e_apps(self):
        ListaApp.objects.create(lista=self.l_casa, app=AppIPTV.objects.create(nome='Clouddy'), aparelho='Quarto')
        resposta = self.client.get(reverse('clientes:lista'))
        self.assertContains(resposta, 'Clouddy (Quarto)')
        self.assertContains(resposta, 'paga por Marta Souza')
        self.assertContains(resposta, 'Bit e Warez')

    def test_clientes_por_pagador_e_busca_por_pagador(self):
        resposta = self.client.get(reverse('clientes:lista'), {'ver': 'pagador', 'q': 'Marta'})
        self.assertEqual([g['nome'] for g in resposta.context['grupos']], ['Marta Souza'])

    def test_filtro_invalido_vira_todos(self):
        resposta = self.client.get(reverse('clientes:lista'), {'filtro': 'xyz'})
        self.assertEqual(resposta.context['filtro'], 'todos')

    def test_dashboard_mantem_blocos_e_agrupa_cobranca(self):
        self.mensalidade(self.l_marta, -5)
        self.mensalidade(self.l_ana, -6)
        self.mensalidade(self.l_casa, 3, 'pendente')
        self.lista(self.carlos, 'Teste', 'teste1', self.bit, em_teste=True)
        resposta = self.client.get(reverse('dashboard'))
        self.assertEqual(resposta.context['total_cobrar'], Decimal('65'))
        self.assertEqual(len(resposta.context['cobrar']), 1)
        self.assertEqual(resposta.context['qtd_vencendo'], 1)
        for texto in ('Cobrar', 'Em Teste', 'Receita dos últimos 6 meses', 'Lucro estimado', 'Divergências nos painéis', 'modal-pagar'):
            self.assertContains(resposta, texto)
