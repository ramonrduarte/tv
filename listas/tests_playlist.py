from unittest import mock

from django.test import TestCase

from django.urls import reverse

from conferencia import escrita
from conferencia.tests_operacoes import Base

from .models import AppIPTV, ListaApp

LINKS = {'server': 'http://auth.bit.test', 'username': 'b1', 'password': 's1',
         'm3u': 'http://auth.bit.test/get.php?username=b1&password=s1&type=m3u', 'short': 'http://enc.test/abc'}


class PlaylistTests(Base):
    def url(self, lista, **params):
        return reverse('listas:playlist', args=[lista.pk])

    def pedir(self, lista, **params):
        return self.client.get(reverse('listas:playlist', args=[lista.pk]), params)

    def test_bit_usa_m3u_e_link_curto_do_painel(self):
        with mock.patch.object(escrita, '_bit', return_value=LINKS):
            self.assertEqual(self.pedir(self.l_bit, tipo='m3u').json(), {'texto': LINKS['m3u'], 'origem': 'painel'})
            self.assertEqual(self.pedir(self.l_bit, tipo='curto').json()['texto'], 'http://enc.test/abc')

    def test_knewcms_nao_tem_m3u_nem_link_curto(self):
        resposta = self.pedir(self.l_knew, tipo='m3u')
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('knewcms não usa lista M3U', resposta.json()['erro'])
        self.assertEqual(self.pedir(self.l_knew, tipo='curto').status_code, 400)

    def test_cartao_do_knewcms_nao_mostra_botoes_de_m3u(self):
        self.l_bit.delete()
        resposta = self.client.get(reverse('clientes:detalhe', args=[self.l_knew.cliente_id]))
        self.assertNotContains(resposta, 'Copiar M3U')
        self.assertNotContains(resposta, 'Baixar M3U')
        self.assertContains(resposta, 'Copiar acesso')

    def test_modelo_do_app_com_m3u_e_recusado_no_knewcms(self):
        app = AppIPTV.objects.create(nome='Smart', formato_lista='{m3u}')
        la = ListaApp.objects.create(lista=self.l_knew, app=app)
        self.assertEqual(self.pedir(self.l_knew, tipo='app', app=la.pk).status_code, 400)

    def test_modelo_do_app_com_dados_da_lista_e_do_app(self):
        app = AppIPTV.objects.create(nome='Clouddy', formato_lista='xc://{host}:{porta}|{usuario}|{senha}')
        la = ListaApp.objects.create(lista=self.l_knew, app=app, usuario_app='outro')
        resposta = self.pedir(self.l_knew, tipo='app', app=la.pk).json()
        self.assertEqual(resposta['texto'], 'xc://warez.test:80|outro|s1')

    def test_modelo_com_m3u_busca_no_painel(self):
        app = AppIPTV.objects.create(nome='Smart', formato_lista='{m3u}')
        la = ListaApp.objects.create(lista=self.l_bit, app=app)
        with mock.patch.object(escrita, '_bit', return_value=LINKS):
            self.assertEqual(self.pedir(self.l_bit, tipo='app', app=la.pk).json()['texto'], LINKS['m3u'])

    def test_modelo_sem_links_nao_chama_o_painel(self):
        app = AppIPTV.objects.create(nome='Clouddy', formato_lista='xc://{servidor}|{usuario}|{senha}')
        la = ListaApp.objects.create(lista=self.l_bit, app=app)
        with mock.patch.object(escrita, '_bit') as bit:
            self.assertEqual(self.pedir(self.l_bit, tipo='app', app=la.pk).json()['texto'], 'xc://http://bit.test|b1|s1')
        bit.assert_not_called()

    def test_app_de_outra_lista_nao_e_aceito(self):
        app = AppIPTV.objects.create(nome='X', formato_lista='{usuario}')
        la = ListaApp.objects.create(lista=self.l_bit, app=app)
        self.assertEqual(self.pedir(self.l_knew, tipo='app', app=la.pk).status_code, 404)

    def test_baixar_redireciona_para_a_m3u(self):
        with mock.patch.object(escrita, '_bit', return_value=LINKS):
            resposta = self.pedir(self.l_bit, tipo='m3u', baixar='1')
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], LINKS['m3u'])

    def test_exige_login(self):
        self.client.logout()
        self.assertEqual(self.pedir(self.l_bit, tipo='m3u').status_code, 302)

    def test_cartao_do_cliente_mostra_blocos_e_botoes(self):
        app = AppIPTV.objects.create(nome='Clouddy', formato_lista='xc://{servidor}|{usuario}|{senha}')
        ListaApp.objects.create(lista=self.l_bit, app=app)
        resposta = self.client.get(reverse('clientes:detalhe', args=[self.l_bit.cliente_id]))
        for texto in ('Copiar acesso', 'Copiar M3U', 'Copiar link curto', 'Baixar M3U', 'Copiar lista do app',
                      'Validade no painel', 'Pacote', 'Alterar usuário ou senha', 'Financeiro'):
            self.assertContains(resposta, texto)

    def test_formulario_do_app_tem_modelo_de_lista(self):
        resposta = self.client.get(reverse('listas:app_iptv_novo'))
        self.assertContains(resposta, 'Modelo de lista')
        self.assertContains(resposta, '{curto}')


class ServidorSemDnsTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_user('u2', password='x'))

    def test_servidor_so_com_nome_e_dns_ficticio_some(self):
        from listas.models import Servidor
        servidor = Servidor.objects.create(nome='Warez')
        self.assertEqual((servidor.endereco, str(servidor)), ('', 'Warez'))
        resposta = self.client.post(reverse('listas:servidor_novo'), {'nome': 'Outro painel', 'ativo': 'on'})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Servidor.objects.get(nome='Outro painel').endereco, '')
        self.assertContains(self.client.get(reverse('listas:servidores')), 'No aplicativo de cada lista')

    def test_cadastro_do_servidor_nao_pede_dns(self):
        resposta = self.client.get(reverse('listas:servidor_novo'))
        self.assertNotIn('dns', resposta.context['form'].fields)
        self.assertNotContains(resposta, 'Endereço (DNS)')
