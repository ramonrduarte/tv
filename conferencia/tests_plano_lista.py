from unittest import mock

from django.urls import reverse

from . import escrita
from .models import AcessoPainel, PacoteLista, PlanoRenovacaoLista
from .operacoes import candidatas, pacotes_do_painel, planos_bit_disponiveis
from .regras import calcular_divergencias
from .tests_operacoes import Base

PLANOS_API = {'data': [{'id': 'p-completa', 'title': 'Lista Completa'}, {'id': 'p-30', 'title': 'Plano 30'}]}
PACOTES_API = {'data': [{'id': 'pk-1', 'title': 'Full HD + H265 + HD + SD'}, {'id': 'pk-2', 'title': 'HD + SD'}]}


class PlanoDeRenovacaoTests(Base):
    def test_planos_do_bit_vem_da_api_e_ficam_em_cache(self):
        with mock.patch.object(escrita, '_bit', return_value=PLANOS_API) as bit:
            self.assertEqual(planos_bit_disponiveis(), [('p-completa', 'Lista Completa'), ('p-30', 'Plano 30')])
            planos_bit_disponiveis()
        self.assertEqual(bit.call_count, 1)

    def test_renovar_mostra_o_plano_da_lista(self):
        PlanoRenovacaoLista.objects.create(lista=self.l_bit, plano_bit='p-30', nome='Plano 30')
        item = [i for i in candidatas('todas') if i['lista'] == self.l_bit][0]
        self.assertEqual(item['plano'], 'Plano 30')
        with mock.patch.object(escrita, '_bit', side_effect=[PLANOS_API, {'credits': 9}]):
            resposta = self.client.post(reverse('conferencia:renovar_conferir'), {'lista': [self.l_bit.pk], 'meses': '1'})
        self.assertEqual(resposta.context['itens'][0]['plano_sugerido'], 'p-30')

    def test_plano_do_bit_nao_aparece_no_cadastro_da_lista(self):
        with mock.patch.object(escrita, '_bit', return_value=PACOTES_API):
            resposta = self.client.get(reverse('listas:editar', args=[self.l_bit.pk]))
        self.assertNotIn('plano_bit', resposta.context['form'].fields)
        self.assertNotContains(resposta, 'Lista Completa')


class PacoteDaListaTests(Base):
    def dados_formulario(self, lista, **extra):
        dados = {
            'cliente': lista.cliente_id, 'servidor': lista.servidor_id, 'nome': lista.nome, 'usuario': lista.usuario,
            'senha': lista.senha, 'num_telas': 1, 'data_ativacao': '2026-01-10', 'ativa': 'on',
        }
        dados.update(extra)
        return dados

    def test_pacotes_de_cada_painel(self):
        with mock.patch.object(escrita, '_bit', return_value=PACOTES_API) as bit:
            self.assertEqual(pacotes_do_painel('bit'), [('pk-1', 'Full HD + H265 + HD + SD'), ('pk-2', 'HD + SD')])
        bit.assert_called_once_with('GET', '/packages')
        nomes = [n for _, n in pacotes_do_painel('knewcms')]
        self.assertIn('Essencial 2 IPTV + 1 P2P', nomes)
        self.assertIn('Ultra 1 Krator+', nomes)

    def test_formulario_traz_o_pacote_do_painel_e_salva(self):
        AcessoPainel.objects.filter(usuario='b1').update(pacote='Full HD + H265 + HD + SD')
        with mock.patch.object(escrita, '_bit', return_value=PACOTES_API):
            resposta = self.client.get(reverse('listas:editar', args=[self.l_bit.pk]))
            self.assertEqual(resposta.context['form'].fields['pacote_bit'].initial, 'pk-1')
            self.assertContains(resposta, 'Pacote do BIT')
            self.assertContains(resposta, 'Pacote do knewcms')
            self.client.post(reverse('listas:editar', args=[self.l_bit.pk]), self.dados_formulario(self.l_bit, pacote_bit='pk-2'))
        salvo = PacoteLista.objects.get(lista=self.l_bit)
        self.assertEqual((salvo.painel, salvo.pacote_id, salvo.nome), ('bit', 'pk-2', 'HD + SD'))

    def test_knewcms_usa_os_pacotes_do_knewcms(self):
        AcessoPainel.objects.filter(usuario='k1').update(pacote='Essencial 2 IPTV + 1 P2P')
        resposta = self.client.get(reverse('listas:editar', args=[self.l_knew.pk]))
        self.assertEqual(resposta.context['form'].fields['pacote_knewcms'].initial, '2')
        self.client.post(reverse('listas:editar', args=[self.l_knew.pk]), self.dados_formulario(self.l_knew, pacote_knewcms='11', pacote_bit='pk-1'))
        salvo = PacoteLista.objects.get(lista=self.l_knew)
        self.assertEqual((salvo.painel, salvo.nome), ('knewcms', 'Ultra 1 Krator+'))

    def test_deixar_em_branco_remove_o_pacote(self):
        PacoteLista.objects.create(lista=self.l_knew, painel='knewcms', pacote_id='2', nome='Essencial 2 IPTV + 1 P2P')
        self.client.post(reverse('listas:editar', args=[self.l_knew.pk]), self.dados_formulario(self.l_knew, pacote_knewcms=''))
        self.assertFalse(PacoteLista.objects.exists())

    def test_pacote_diferente_do_painel_vira_aviso_e_aparece_no_cartao(self):
        AcessoPainel.objects.filter(usuario='k1').update(pacote='Essencial 2 IPTV + 1 P2P')
        PacoteLista.objects.create(lista=self.l_knew, painel='knewcms', pacote_id='11', nome='Ultra 1 Krator+')
        achado = [a for a in calcular_divergencias()[0] if a.tipo == 'pacote'][0]
        self.assertIn('Pacote no painel: Essencial 2 IPTV + 1 P2P · no cadastro: Ultra 1 Krator+', achado.detalhe)
        resposta = self.client.get(reverse('clientes:detalhe', args=[self.l_knew.cliente_id]))
        self.assertContains(resposta, 'Ultra 1 Krator+')
        self.assertContains(resposta, 'No painel: Essencial 2 IPTV + 1 P2P')

    def test_sem_cadastro_mostra_o_pacote_do_painel(self):
        AcessoPainel.objects.filter(usuario='b1').update(pacote='HD + SD')
        resposta = self.client.get(reverse('listas:detalhe', args=[self.l_bit.pk]))
        self.assertContains(resposta, 'HD + SD')
        self.assertFalse([a for a in calcular_divergencias()[0] if a.tipo == 'pacote'])
