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
            self.assertContains(resposta, 'Plano no BIT (usado na renovação)')
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
