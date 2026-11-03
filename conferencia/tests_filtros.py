from unittest import mock

from django.urls import reverse

from clientes.models import Cliente, Pagador
from listas.models import ListaCanais, Servidor

from . import escrita
from .leitura import salvar_leitura
from .operacoes import candidatas
from .tests_operacoes import Base, acesso


class FiltrosRenovacaoTests(Base):
    def setUp(self):
        super().setUp()
        marta = Pagador.objects.create(nome='Marta Souza')
        ana = Cliente.objects.create(nome='Ana Souza', apelido='Aninha', whatsapp='5551988887777')
        bit = Servidor.objects.get(nome='Bit')
        self.l_ana = ListaCanais.objects.create(cliente=ana, servidor=bit, pagador=marta, nome='Sala', usuario='anasala', senha='s1')
        salvar_leitura('bit', [acesso('b1'), acesso('anasala', dias=60, observacao='TV da sala')])

    def usuarios(self, **kwargs):
        return {i['lista'].usuario for i in candidatas(**kwargs)}

    def test_busca_por_pagador_apelido_whatsapp_login_e_observacao(self):
        for termo in ('marta', 'aninha', '88887777', 'anasala', 'tv da sala', 'souza sala'):
            self.assertEqual(self.usuarios(filtro='todas', busca=termo), {'anasala'}, termo)

    def test_busca_ignora_acento_e_maiusculas(self):
        self.assertEqual(self.usuarios(filtro='todas', busca='SÓUZA'), {'anasala'})

    def test_filtro_por_painel(self):
        self.assertEqual(self.usuarios(filtro='todas', painel='knewcms'), {'k1', 'k2'})

    def test_busca_na_tela_mostra_qualquer_validade(self):
        resposta = self.client.get(reverse('conferencia:renovar'), {'q': 'marta'})
        self.assertEqual(resposta.context['filtro'], 'todas')
        self.assertEqual([i['lista'].usuario for i in resposta.context['itens']], ['anasala'])
        self.assertContains(resposta, 'paga por Marta Souza')

    def test_pagina_do_cliente_permite_renovar_e_alterar(self):
        resposta = self.client.get(reverse('clientes:detalhe', args=[self.l_knew.cliente_id]))
        self.assertContains(resposta, 'Renovar nos painéis')
        self.assertContains(resposta, 'Alterar no painel')
        self.assertEqual({l.usuario for l in resposta.context['renovaveis']}, {'k1', 'k2', 'b1'})

    def test_renovacao_pelo_cliente_volta_para_o_cliente(self):
        voltar = reverse('clientes:detalhe', args=[self.l_knew.cliente_id])
        resposta = self.client.post(reverse('conferencia:renovar_conferir'), {'lista': [self.l_knew.pk], 'meses': '1', 'voltar': voltar})
        self.assertEqual(resposta.context['voltar'], voltar)
        dados = {'lote': resposta.context['lote'], 'meses': '1', 'lista': [self.l_knew.pk], 'voltar': voltar}
        with mock.patch.object(escrita, '_knewcms', return_value={}):
            resposta = self.client.post(reverse('conferencia:renovar_executar'), dados)
        self.assertContains(resposta, f'href="{voltar}"')
        sem_lista = self.client.post(reverse('conferencia:renovar_conferir'), {'meses': '1', 'voltar': voltar})
        self.assertRedirects(sem_lista, voltar, fetch_redirect_response=False)

    def test_voltar_para_outro_site_e_ignorado(self):
        resposta = self.client.post(reverse('conferencia:renovar_conferir'), {'meses': '1', 'voltar': 'https://exemplo.com/'})
        self.assertRedirects(resposta, reverse('conferencia:renovar'))

    def test_alterar_pelo_cliente_volta_para_o_cliente(self):
        voltar = reverse('clientes:detalhe', args=[self.l_bit.cliente_id])
        with mock.patch.object(escrita, '_bit', return_value={'password': 'nova'}):
            resposta = self.client.post(
                reverse('conferencia:acesso_editar', args=[self.l_bit.pk]),
                {'gerar_senha': '1', 'confirmo': '1', 'voltar': voltar, 'novo_usuario': 'b1'},
            )
        self.assertRedirects(resposta, voltar, fetch_redirect_response=False)
