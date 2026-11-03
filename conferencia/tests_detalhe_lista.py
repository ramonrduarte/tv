from unittest import mock

from django.test import override_settings
from django.urls import reverse

from . import escrita
from .leitura import LeituraInvalida
from .models import OperacaoPainel, PlanoRenovacaoLista
from .tests_operacoes import Base

LINKS = {'server': 'http://auth.exemplo.test', 'username': 'b1', 'password': 'x',
         'm3u': 'http://auth.exemplo.test/get.php?username=b1&type=m3u', 'short': 'http://enc.test/abc'}


class DetalheDaListaTests(Base):
    def url(self, lista):
        return reverse('listas:detalhe', args=[lista.pk])

    def test_mostra_painel_plano_e_historico(self):
        PlanoRenovacaoLista.objects.create(lista=self.l_bit, plano_bit='p-30', nome='Plano 30')
        OperacaoPainel.objects.create(lista=self.l_bit, painel='bit', usuario_painel='b1', tipo='renovacao', detalhe='1 mês · Plano 30', status='ok')
        with mock.patch.object(escrita, '_bit') as bit:
            resposta = self.client.get(self.url(self.l_bit))
        bit.assert_not_called()
        self.assertContains(resposta, 'Plano 30')
        self.assertContains(resposta, 'Histórico no painel e no cadastro')
        self.assertContains(resposta, 'Mostrar links M3U')

    def test_links_do_bit_so_quando_pedidos(self):
        with mock.patch.object(escrita, '_bit', return_value=LINKS) as bit:
            resposta = self.client.get(self.url(self.l_bit), {'links': '1'})
        bit.assert_called_once_with('GET', '/lines/b1/links')
        self.assertContains(resposta, 'Lista M3U completa')
        self.assertContains(resposta, 'http://enc.test/abc')
        self.assertContains(resposta, 'Baixar lista M3U')

    def test_erro_dos_links_aparece_sem_quebrar(self):
        with mock.patch.object(escrita, '_bit', side_effect=LeituraInvalida('403 IP')):
            resposta = self.client.get(self.url(self.l_bit), {'links': '1'})
        self.assertContains(resposta, 'Não foi possível ler os links')

    def test_knewcms_nao_tem_botao_de_links(self):
        self.assertNotContains(self.client.get(self.url(self.l_knew)), 'Mostrar links M3U')

    @override_settings(BIT_API_TOKEN='')
    def test_sem_chave_nao_mostra_links(self):
        self.assertNotContains(self.client.get(self.url(self.l_bit)), 'Mostrar links M3U')
