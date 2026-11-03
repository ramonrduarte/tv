from unittest import mock

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

    def test_knewcms_monta_m3u_no_padrao_xtream_e_nao_tem_link_curto(self):
        resposta = self.pedir(self.l_knew, tipo='m3u').json()
        self.assertEqual(resposta['texto'], 'http://warez.test:80/get.php?username=k1&password=s1&type=m3u_plus&output=ts')
        self.assertEqual(resposta['origem'], 'montada')
        self.assertEqual(self.pedir(self.l_knew, tipo='curto').status_code, 400)

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
            self.assertEqual(self.pedir(self.l_bit, tipo='app', app=la.pk).json()['texto'], 'xc://http://bit.test:80|b1|s1')
        bit.assert_not_called()

    def test_app_de_outra_lista_nao_e_aceito(self):
        app = AppIPTV.objects.create(nome='X', formato_lista='{usuario}')
        la = ListaApp.objects.create(lista=self.l_bit, app=app)
        self.assertEqual(self.pedir(self.l_knew, tipo='app', app=la.pk).status_code, 404)

    def test_baixar_redireciona_para_a_m3u(self):
        resposta = self.pedir(self.l_knew, tipo='m3u', baixar='1')
        self.assertEqual(resposta.status_code, 302)
        self.assertIn('get.php?username=k1', resposta['Location'])

    def test_exige_login(self):
        self.client.logout()
        self.assertEqual(self.pedir(self.l_knew, tipo='m3u').status_code, 302)

    def test_cartao_do_cliente_mostra_blocos_e_botoes(self):
        app = AppIPTV.objects.create(nome='Clouddy', formato_lista='xc://{servidor}|{usuario}|{senha}')
        ListaApp.objects.create(lista=self.l_bit, app=app)
        resposta = self.client.get(reverse('clientes:detalhe', args=[self.l_bit.cliente_id]))
        for texto in ('Copiar acesso', 'Copiar M3U', 'Copiar link curto', 'Baixar M3U', 'Copiar lista do app',
                      'Validade no painel', 'Plano no BIT', 'Alterar usuário ou senha', 'Financeiro'):
            self.assertContains(resposta, texto)

    def test_formulario_do_app_tem_modelo_de_lista(self):
        resposta = self.client.get(reverse('listas:app_iptv_novo'))
        self.assertContains(resposta, 'Modelo de lista')
        self.assertContains(resposta, '{curto}')
