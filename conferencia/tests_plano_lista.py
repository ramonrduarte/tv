from unittest import mock

from django.core.cache import cache
from django.urls import reverse

from . import escrita
from .models import AcessoPainel, PlanoRenovacaoLista
from .operacoes import candidatas, planos_bit_disponiveis
from .tests_operacoes import Base

PLANOS_API = {'data': [{'id': 'p-completa', 'title': 'Lista Completa'}, {'id': 'p-30', 'title': 'Plano 30'}]}


class PlanoNaListaTests(Base):
    def dados_formulario(self, lista, **extra):
        dados = {
            'cliente': lista.cliente_id, 'servidor': lista.servidor_id, 'nome': lista.nome, 'usuario': lista.usuario,
            'senha': lista.senha, 'num_telas': 1, 'data_ativacao': '2026-01-10', 'ativa': 'on',
        }
        dados.update(extra)
        return dados

    def test_planos_do_bit_vem_da_api_e_ficam_em_cache(self):
        with mock.patch.object(escrita, '_bit', return_value=PLANOS_API) as bit:
            self.assertEqual(planos_bit_disponiveis(), [('p-completa', 'Lista Completa'), ('p-30', 'Plano 30')])
            planos_bit_disponiveis()
        self.assertEqual(bit.call_count, 1)

    def test_editar_lista_escolhe_e_salva_o_plano_do_bit(self):
        AcessoPainel.objects.filter(usuario='b1').update(pacote='Full HD + H265 + HD + SD')
        with mock.patch.object(escrita, '_bit', return_value=PLANOS_API):
            resposta = self.client.get(reverse('listas:editar', args=[self.l_bit.pk]))
            self.assertContains(resposta, 'Plano no painel (usado na renovação)')
            self.assertContains(resposta, 'Full HD + H265 + HD + SD')
            self.assertContains(resposta, 'Plano de cobrança')
            self.client.post(reverse('listas:editar', args=[self.l_bit.pk]), self.dados_formulario(self.l_bit, plano_bit='p-30'))
        salvo = PlanoRenovacaoLista.objects.get(lista=self.l_bit)
        self.assertEqual((salvo.plano_bit, salvo.nome), ('p-30', 'Plano 30'))

    def test_criar_lista_com_plano_do_bit(self):
        dados = self.dados_formulario(self.l_bit, nome='nova', usuario='novo1', senha='x', plano_bit='p-completa')
        with mock.patch.object(escrita, '_bit', return_value=PLANOS_API):
            self.client.post(reverse('listas:nova'), dados)
        self.assertEqual(PlanoRenovacaoLista.objects.get(lista__usuario='novo1').nome, 'Lista Completa')

    def test_deixar_em_branco_remove_o_plano(self):
        PlanoRenovacaoLista.objects.create(lista=self.l_bit, plano_bit='p-30', nome='Plano 30')
        with mock.patch.object(escrita, '_bit', return_value=PLANOS_API):
            self.client.post(reverse('listas:editar', args=[self.l_bit.pk]), self.dados_formulario(self.l_bit, plano_bit=''))
        self.assertFalse(PlanoRenovacaoLista.objects.exists())

    def test_sem_api_mantem_o_plano_salvo_como_opcao(self):
        PlanoRenovacaoLista.objects.create(lista=self.l_bit, plano_bit='p-30', nome='Plano 30')
        cache.clear()
        with mock.patch.object(escrita, '_bit', side_effect=escrita.LeituraInvalida('fora')):
            resposta = self.client.get(reverse('listas:editar', args=[self.l_bit.pk]))
        self.assertIn(('p-30', 'Plano 30'), resposta.context['form'].fields['plano_bit'].choices)
        self.assertEqual(resposta.context['form'].fields['plano_bit'].initial, 'p-30')

    def test_renovar_mostra_o_plano_da_lista(self):
        PlanoRenovacaoLista.objects.create(lista=self.l_bit, plano_bit='p-30', nome='Plano 30')
        item = [i for i in candidatas('todas') if i['lista'] == self.l_bit][0]
        self.assertEqual(item['plano'], 'Plano 30')
        with mock.patch.object(escrita, '_bit', side_effect=[PLANOS_API, {'credits': 9}]):
            resposta = self.client.post(reverse('conferencia:renovar_conferir'), {'lista': [self.l_bit.pk], 'meses': '1'})
        self.assertEqual(resposta.context['itens'][0]['plano_sugerido'], 'p-30')


class PlanoNoPainelTests(Base):
    def test_knewcms_mostra_o_plano_do_painel_sem_campo_para_escolher(self):
        from .models import AcessoPainel as Acesso
        Acesso.objects.filter(usuario='k1').update(plano='Essencial 2 IPTV + 1 P2P')
        resposta = self.client.get(reverse('listas:editar', args=[self.l_knew.pk]))
        self.assertNotIn('plano_bit', resposta.context['form'].fields)
        self.assertContains(resposta, 'Essencial 2 IPTV + 1 P2P')
        cliente = self.client.get(reverse('clientes:detalhe', args=[self.l_knew.cliente_id]))
        self.assertContains(cliente, 'Essencial 2 IPTV + 1 P2P')

    def test_bit_sem_plano_usa_o_das_listas_com_mesmo_pacote(self):
        from listas.models import ListaCanais
        from .models import AcessoPainel as Acesso
        from .operacoes import plano_da_lista, plano_sugerido
        outra = ListaCanais.objects.create(cliente=self.l_bit.cliente, servidor=self.l_bit.servidor, nome='b2', usuario='b2', senha='x')
        Acesso.objects.create(painel='bit', usuario='b2', pacote='Full HD')
        Acesso.objects.filter(usuario='b1').update(pacote='Full HD')
        PlanoRenovacaoLista.objects.create(lista=outra, plano_bit='p-completa', nome='Lista Completa')
        acesso = Acesso.objects.get(usuario='b1')
        self.assertEqual(plano_da_lista(self.l_bit, acesso), ('Lista Completa', 'sugerido'))
        self.assertEqual(plano_sugerido(self.l_bit, acesso, [('p-completa', 'Lista Completa'), ('p-30', 'Plano 30')]), 'p-completa')
        with mock.patch.object(escrita, '_bit', return_value=PLANOS_API):
            resposta = self.client.get(reverse('listas:editar', args=[self.l_bit.pk]))
        self.assertEqual(resposta.context['form'].fields['plano_bit'].initial, 'p-completa')
