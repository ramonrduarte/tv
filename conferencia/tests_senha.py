from unittest import mock

from django.test import override_settings
from django.urls import reverse

from . import escrita
from .leitura import assinar_senha
from .models import AcessoPainel, OperacaoPainel
from .tests_operacoes import Base


class SenhaTravadaTests(Base):
    def test_lista_no_painel_nao_deixa_mudar_a_senha_no_formulario(self):
        resposta = self.client.get(reverse('listas:editar', args=[self.l_bit.pk]))
        self.assertTrue(resposta.context['form'].fields['senha'].disabled)
        self.assertContains(resposta, 'Gerar nova ou trazer a atual do painel')
        dados = {k: v for k, v in resposta.context['form'].initial.items() if v is not None}
        dados.update({'cliente': self.l_bit.cliente_id, 'servidor': self.l_bit.servidor_id, 'senha': 'invasora',
                      'data_ativacao': '2026-01-10', 'nome': 'b1', 'usuario': 'b1', 'num_telas': 1, 'ativa': 'on'})
        dados = {k: v for k, v in dados.items() if k not in ('ultima_atualizacao', 'controle_desde', 'data_inicio_teste', 'plano', 'pagador')}
        self.client.post(reverse('listas:editar', args=[self.l_bit.pk]), dados)
        self.l_bit.refresh_from_db()
        self.assertEqual(self.l_bit.senha, 's1')

    @override_settings(BIT_API_TOKEN='')
    def test_sem_chave_da_api_a_senha_continua_editavel(self):
        resposta = self.client.get(reverse('listas:editar', args=[self.l_bit.pk]))
        self.assertFalse(resposta.context['form'].fields['senha'].disabled)

    def test_lista_fora_dos_paineis_continua_editavel(self):
        AcessoPainel.objects.filter(usuario='b1').delete()
        resposta = self.client.get(reverse('listas:editar', args=[self.l_bit.pk]))
        self.assertFalse(resposta.context['form'].fields['senha'].disabled)


class TrazerSenhaTests(Base):
    def url(self, lista):
        return reverse('conferencia:acesso_editar', args=[lista.pk])

    def test_traz_a_senha_do_bit_sem_alterar_o_painel(self):
        with mock.patch.object(escrita, '_bit', return_value={'username': 'b1', 'password': 'dopainel'}) as bit:
            resposta = self.client.post(self.url(self.l_bit), {'acao': 'trazer_senha'}, follow=True)
        bit.assert_called_once_with('GET', '/lines/b1')
        self.l_bit.refresh_from_db()
        self.assertEqual(self.l_bit.senha, 'dopainel')
        self.assertEqual(AcessoPainel.objects.get(usuario='b1').senha_hash, assinar_senha('dopainel'))
        self.assertContains(resposta, 'Nada foi alterado no painel')
        self.assertEqual(OperacaoPainel.objects.get().tipo, 'copia')

    def test_traz_a_senha_do_knewcms_pelo_id(self):
        busca = {'items': [{'id': 99, 'username': 'k1', 'password': 'errada'}, {'id': 11, 'username': 'k1', 'password': 'certa'}]}
        with mock.patch.object(escrita, '_knewcms', return_value=busca):
            self.client.post(self.url(self.l_knew), {'acao': 'trazer_senha'})
        self.l_knew.refresh_from_db()
        self.assertEqual(self.l_knew.senha, 'certa')

    def test_falha_nao_muda_a_lista(self):
        with mock.patch.object(escrita, '_bit', return_value={}):
            resposta = self.client.post(self.url(self.l_bit), {'acao': 'trazer_senha'}, follow=True)
        self.l_bit.refresh_from_db()
        self.assertEqual(self.l_bit.senha, 's1')
        self.assertContains(resposta, 'não devolveu a senha')
        self.assertEqual(OperacaoPainel.objects.get().status, 'falha')
