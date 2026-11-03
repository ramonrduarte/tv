from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from listas.models import AppIPTV, ListaApp, ListaCanais, Servidor

from . import escrita
from .leitura import LeituraInvalida, SemResposta, assinar_senha, salvar_leitura
from .models import AcessoPainel, ConfiguracaoConferencia, OperacaoPainel, PlanoRenovacaoLista
from .operacoes import candidatas, executar_renovacao

TOKENS = {'WWPANEL_API_TOKEN': 'k', 'BIT_API_TOKEN': 'bit_x'}


def acesso(usuario, dias=3, **extra):
    dados = {'usuario': usuario, 'senha_hash': assinar_senha('s1'), 'ativo': True,
             'validade': timezone.now() + timedelta(days=dias), 'telas': 1}
    dados.update(extra)
    return dados


@override_settings(**TOKENS)
class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('ramon', password='x')
        self.client.force_login(self.user)
        bit = Servidor.objects.create(nome='Bit', dns='bit.test')
        warez = Servidor.objects.create(nome='Warez', dns='warez.test')
        cliente = Cliente.objects.create(nome='Carlos Prado', whatsapp='5551900000001')
        criar = lambda u, s, **e: ListaCanais.objects.create(cliente=cliente, servidor=s, nome=u, usuario=u, senha='s1', data_ativacao=date(2026, 1, 10), **e)
        self.l_knew = criar('k1', warez)
        self.l_bit = criar('b1', bit)
        self.l_longe = criar('k2', warez)
        ListaApp.objects.create(lista=self.l_bit, app=AppIPTV.objects.create(nome='Smarters'))
        salvar_leitura('knewcms', [acesso('k1', painel_id='11'), acesso('k2', dias=40, painel_id='12')])
        salvar_leitura('bit', [acesso('b1')])

    def nova_validade(self):
        return timezone.now() + timedelta(days=33)


class RenovacaoTests(Base):
    def test_candidatas_filtra_vencendo(self):
        self.assertEqual({i['lista'].usuario for i in candidatas('vencendo')}, {'k1', 'b1'})
        self.assertEqual(len(candidatas('todas')), 3)

    def test_renova_nos_dois_paineis_e_registra(self):
        validade = self.nova_validade()
        with mock.patch.object(escrita, '_knewcms', return_value={'exp_date': validade.isoformat()}) as knew, \
             mock.patch.object(escrita, '_bit', return_value={'line': {'expiresAt': validade.isoformat()}, 'credits': 41}) as bit:
            resultado = executar_renovacao([self.l_knew.pk, self.l_bit.pk], 1, {self.l_bit.pk: 'plano-1'}, self.user)
        knew.assert_called_once_with('PATCH', '/lines/v2/extend/11', corpo={'months': 1})
        bit.assert_called_once_with('POST', '/lines/b1/renew', corpo={'planId': 'plano-1', 'periodInMonths': 1})
        self.assertEqual(resultado['creditos_bit'], 41)
        self.assertEqual(OperacaoPainel.objects.filter(status='ok').count(), 2)
        self.assertEqual(AcessoPainel.objects.get(usuario='k1').validade.date(), validade.date())

    def test_nao_renova_de_novo_logo_depois(self):
        with mock.patch.object(escrita, '_knewcms', return_value={'exp_date': None}) as knew:
            executar_renovacao([self.l_knew.pk], 1, {}, self.user)
            resultado = executar_renovacao([self.l_knew.pk], 1, {}, self.user)
        self.assertEqual(knew.call_count, 1)
        self.assertIn('há poucos minutos', resultado['itens'][0]['motivo'])

    def test_sem_resposta_fica_incerta_e_bloqueia_nova_tentativa(self):
        with mock.patch.object(escrita, '_knewcms', side_effect=SemResposta('caiu')) as knew:
            executar_renovacao([self.l_knew.pk], 1, {}, self.user)
            executar_renovacao([self.l_knew.pk], 1, {}, self.user)
        self.assertEqual(knew.call_count, 1)
        self.assertEqual(OperacaoPainel.objects.get().status, 'incerta')

    def test_recusa_do_painel_fica_como_falha_e_permite_tentar_de_novo(self):
        with mock.patch.object(escrita, '_knewcms', side_effect=LeituraInvalida('402 sem créditos')) as knew:
            executar_renovacao([self.l_knew.pk], 1, {}, self.user)
            executar_renovacao([self.l_knew.pk], 1, {}, self.user)
        self.assertEqual(knew.call_count, 2)
        self.assertEqual(set(OperacaoPainel.objects.values_list('status', flat=True)), {'falha'})

    def test_bit_sem_plano_nao_e_enviado(self):
        with mock.patch.object(escrita, '_bit') as bit:
            executar_renovacao([self.l_bit.pk], 1, {}, self.user)
        bit.assert_not_called()
        self.assertEqual(OperacaoPainel.objects.get().status, 'falha')

    @override_settings(BIT_API_TOKEN='')
    def test_sem_token_nao_envia(self):
        with mock.patch.object(escrita, '_bit') as bit:
            resultado = executar_renovacao([self.l_bit.pk], 1, {self.l_bit.pk: 'p'}, self.user)
        bit.assert_not_called()
        self.assertIn('BIT_API_TOKEN', resultado['itens'][0]['motivo'])
        self.assertFalse(OperacaoPainel.objects.exists())


class TelasRenovacaoTests(Base):
    def test_fluxo_conferir_e_enviar_uma_vez_so(self):
        with mock.patch.object(escrita, '_bit', side_effect=[{'data': [{'id': 'p1', 'title': 'Mensal'}]}, {'credits': 50}]):
            resposta = self.client.post(reverse('conferencia:renovar_conferir'), {'lista': [self.l_knew.pk, self.l_bit.pk], 'meses': '1'})
        self.assertContains(resposta, 'Saldo atual: 50 créditos')
        self.assertContains(resposta, 'Mensal')
        lote = resposta.context['lote']
        dados = {'lote': lote, 'meses': '1', 'lista': [self.l_knew.pk, self.l_bit.pk], f'plano_{self.l_bit.pk}': 'p1'}
        with mock.patch.object(escrita, '_knewcms', return_value={}) as knew, \
             mock.patch.object(escrita, '_bit', return_value={'line': {}, 'credits': 49}) as bit:
            resposta = self.client.post(reverse('conferencia:renovar_executar'), dados)
            self.assertContains(resposta, 'Saldo do BIT depois da renovação: 49')
            segunda = self.client.post(reverse('conferencia:renovar_executar'), dados)
        self.assertEqual((knew.call_count, bit.call_count), (1, 1))
        self.assertRedirects(segunda, reverse('conferencia:renovar'))
        self.assertEqual(PlanoRenovacaoLista.objects.get(lista=self.l_bit).plano_bit, 'p1')

    def test_meses_invalidos_e_limite(self):
        resposta = self.client.post(reverse('conferencia:renovar_conferir'), {'lista': [self.l_knew.pk], 'meses': '5'})
        self.assertRedirects(resposta, reverse('conferencia:renovar'))

    def test_tela_lista_vencendo_e_historico(self):
        OperacaoPainel.objects.create(lista=self.l_knew, painel='knewcms', usuario_painel='k1', tipo='renovacao', status='ok')
        resposta = self.client.get(reverse('conferencia:renovar'))
        self.assertContains(resposta, 'Conferir antes de enviar')
        self.assertContains(resposta, 'Últimas operações nos painéis')
        self.assertNotContains(resposta, '>k2<')

    def test_exige_post_e_login(self):
        self.assertEqual(self.client.get(reverse('conferencia:renovar_executar')).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('conferencia:renovar')).status_code, 302)


class AlterarAcessoTests(Base):
    def url(self, lista):
        return reverse('conferencia:acesso_editar', args=[lista.pk])

    def test_knewcms_troca_senha_mantendo_whatsapp_e_pais(self):
        busca = {'items': [{'id': 11, 'username': 'k1', 'whatsapp': '+5551', 'country': 'Brasil', 'notes': 'Sala'}]}
        with mock.patch.object(escrita, '_knewcms', side_effect=[busca, {}]) as knew:
            resposta = self.client.post(self.url(self.l_knew), {'nova_senha': 'nova123', 'confirmo': '1'}, follow=True)
        knew.assert_any_call('PATCH', '/lines/11', corpo={'password': 'nova123', 'whatsapp': '+5551', 'country': 'Brasil', 'notes': 'Sala'})
        self.l_knew.refresh_from_db()
        self.assertEqual(self.l_knew.senha, 'nova123')
        self.assertEqual(AcessoPainel.objects.get(usuario='k1').senha_hash, assinar_senha('nova123'))
        self.assertContains(resposta, 'Senha alterada')
        self.assertNotIn('nova123', OperacaoPainel.objects.get().detalhe)

    def test_bit_troca_usuario_e_gera_senha(self):
        with mock.patch.object(escrita, '_bit', side_effect=[{}, {'password': 'sorteada'}]) as bit:
            resposta = self.client.post(self.url(self.l_bit), {'novo_usuario': 'b1novo', 'gerar_senha': '1', 'confirmo': '1'}, follow=True)
        self.assertEqual(bit.call_args_list[0].args, ('PATCH', '/lines/b1'))
        self.assertEqual(bit.call_args_list[1].args, ('POST', '/lines/b1novo/password'))
        self.l_bit.refresh_from_db()
        self.assertEqual((self.l_bit.usuario, self.l_bit.senha), ('b1novo', 'sorteada'))
        self.assertTrue(AcessoPainel.objects.filter(painel='bit', usuario='b1novo').exists())
        self.assertContains(resposta, 'Atualize também nos aplicativos: Smarters')

    def test_recusa_do_painel_nao_muda_a_lista(self):
        with mock.patch.object(escrita, '_bit', side_effect=LeituraInvalida('409 USERNAME_TAKEN')):
            resposta = self.client.post(self.url(self.l_bit), {'novo_usuario': 'outro1', 'confirmo': '1'}, follow=True)
        self.l_bit.refresh_from_db()
        self.assertEqual(self.l_bit.usuario, 'b1')
        self.assertContains(resposta, 'USERNAME_TAKEN')
        self.assertEqual(OperacaoPainel.objects.get().status, 'falha')

    def test_sem_confirmacao_nao_envia(self):
        with mock.patch.object(escrita, '_knewcms') as knew:
            self.client.post(self.url(self.l_knew), {'nova_senha': 'nova123'})
        knew.assert_not_called()

    def test_tela_mostra_opcoes_de_cada_painel(self):
        self.assertContains(self.client.get(self.url(self.l_bit)), 'Gerar nova senha')
        self.assertContains(self.client.get(self.url(self.l_knew)), 'o usuário não pode ser trocado')
