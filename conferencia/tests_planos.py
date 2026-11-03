from unittest import mock

from django.urls import reverse

from . import escrita
from .leitura import _acesso_bit, _acesso_knewcms
from .models import AcessoPainel, OperacaoPainel, PlanoRenovacaoLista
from .operacoes import executar_renovacao, plano_sugerido
from .tests_operacoes import Base

PLANOS = [('p-completa', 'Lista Completa'), ('p-30', 'Plano 30')]


class PlanoPorListaTests(Base):
    def test_le_o_pacote_dos_dois_paineis(self):
        self.assertEqual(_acesso_bit({'username': 'x', 'package': {'id': '1', 'title': 'Plano 30'}}, False)['pacote'], 'Plano 30')
        self.assertEqual(_acesso_knewcms({'username': 'x', 'plan': {'id': 2, 'name': 'Essencial'}})['plano'], 'Essencial')

    def test_sugere_pelo_pacote_e_depois_usa_o_salvo(self):
        acesso = AcessoPainel.objects.get(usuario='b1')
        acesso.pacote = 'plano 30'
        acesso.save()
        self.assertEqual(plano_sugerido(self.l_bit, acesso, PLANOS), 'p-30')
        PlanoRenovacaoLista.objects.create(lista=self.l_bit, plano_bit='p-completa')
        self.assertEqual(plano_sugerido(self.l_bit, acesso, PLANOS), 'p-completa')

    def test_sem_pacote_conhecido_nao_sugere(self):
        self.assertEqual(plano_sugerido(self.l_bit, AcessoPainel.objects.get(usuario='b1'), PLANOS), '')

    def test_cada_lista_guarda_o_seu_plano_e_knewcms_nao_usa_plano(self):
        with mock.patch.object(escrita, '_knewcms', return_value={}) as knew, \
             mock.patch.object(escrita, '_bit', return_value={'line': {}, 'credits': 1}):
            executar_renovacao([self.l_knew.pk, self.l_bit.pk], 1, {self.l_bit.pk: 'p-30', self.l_knew.pk: 'p-30'}, self.user, dict(PLANOS))
        knew.assert_called_once_with('PATCH', '/lines/v2/extend/11', corpo={'months': 1})
        self.assertEqual(list(PlanoRenovacaoLista.objects.values_list('lista_id', 'nome')), [(self.l_bit.pk, 'Plano 30')])
        self.assertEqual(OperacaoPainel.objects.get(painel='bit').detalhe, '1 mês · Plano 30')

    def test_plano_que_o_bit_nao_ofereceu_e_recusado(self):
        with mock.patch.object(escrita, '_bit', side_effect=[{'data': [{'id': 'p-30', 'title': 'Plano 30'}]}, {'credits': 5}]):
            resposta = self.client.post(reverse('conferencia:renovar_conferir'), {'lista': [self.l_bit.pk], 'meses': '1'})
        dados = {'lote': resposta.context['lote'], 'meses': '1', 'lista': [self.l_bit.pk], f'plano_{self.l_bit.pk}': 'inventado'}
        with mock.patch.object(escrita, '_bit') as bit:
            self.client.post(reverse('conferencia:renovar_executar'), dados)
        bit.assert_not_called()


class HistoricoTests(Base):
    def test_troca_de_usuario_no_cadastro_fica_no_historico_sem_senha(self):
        AcessoPainel.objects.filter(usuario='k1').delete()
        resposta = self.client.get(reverse('listas:editar', args=[self.l_knew.pk]))
        dados = {
            'cliente': self.l_knew.cliente_id, 'servidor': self.l_knew.servidor_id, 'nome': 'k1',
            'usuario': 'k1novo', 'senha': 'outra', 'num_telas': 1, 'data_ativacao': '2026-01-10', 'ativa': 'on',
        }
        self.assertEqual(resposta.status_code, 200)
        self.client.post(reverse('listas:editar', args=[self.l_knew.pk]), dados)
        operacao = OperacaoPainel.objects.get(tipo='cadastro')
        self.assertEqual(operacao.detalhe, 'Usuário: k1 → k1novo · Senha alterada')
        self.assertNotIn('outra', operacao.detalhe)

    def test_pagina_do_cliente_mostra_renovacao_e_troca(self):
        OperacaoPainel.objects.create(lista=self.l_bit, painel='bit', usuario_painel='b1', tipo='renovacao', detalhe='1 mês · Plano 30', status='ok')
        OperacaoPainel.objects.create(lista=self.l_bit, painel='bit', usuario_painel='b1', tipo='senha', status='falha')
        resposta = self.client.get(reverse('clientes:detalhe', args=[self.l_bit.cliente_id]))
        self.assertContains(resposta, 'Renovação no BIT · 1 mês · Plano 30')
        self.assertContains(resposta, 'Troca de senha no BIT')
        self.assertContains(resposta, 'Recusada pelo painel')
