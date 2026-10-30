from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente, Pagador
from listas.models import AppIPTV, ListaApp, ListaCanais, Servidor

from . import leitura
from .bookmarklet import gerar_bookmarklet
from .leitura import LeituraInvalida, assinar_senha, importar_bit, knewcms_na_hora, salvar_leitura
from .models import AcessoPainel, ConfiguracaoConferencia, DivergenciaIgnorada, LeituraPainel, VinculoPainel
from .regras import calcular_divergencias, contar_divergencias, montar_conferencia


def acesso(usuario, senha='s1', **extra):
    dados = {
        'usuario': usuario, 'senha_hash': assinar_senha(senha), 'ativo': True,
        'validade': timezone.now() + timedelta(days=20), 'telas': 1,
    }
    dados.update(extra)
    return dados


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.bit = Servidor.objects.create(nome='Bit', dns='bit.test')
        self.warez = Servidor.objects.create(nome='Warez', dns='warez.test')
        self.outro = Servidor.objects.create(nome='Outro', dns='outro.test')
        self.cliente = Cliente.objects.create(nome='Carlos Prado', whatsapp='5551900000001')

    def lista(self, usuario, servidor=None, cliente=None, **extra):
        dados = {
            'cliente': cliente or self.cliente, 'servidor': servidor or self.bit,
            'nome': usuario, 'usuario': usuario, 'senha': 's1', 'data_ativacao': date(2026, 1, 10),
        }
        dados.update(extra)
        return ListaCanais.objects.create(**dados)

    def tipos(self):
        return {(a.tipo, a.usuario) for a in calcular_divergencias()[0]}


class RegrasTests(Base):
    def test_listas_certas_em_servidores_diferentes_nao_divergem(self):
        self.lista('casa', self.bit)
        self.lista('sitio', self.warez)
        salvar_leitura('bit', [acesso('casa')])
        salvar_leitura('knewcms', [acesso('sitio')])
        self.assertEqual(self.tipos(), set())

    def test_pagador_diferente_nao_afeta_conferencia(self):
        pagador = Pagador.objects.create(nome='Marta Souza')
        outro = Cliente.objects.create(nome='Ana Souza', whatsapp='5551900000002')
        self.lista('ana', self.bit, cliente=outro, pagador=pagador)
        self.lista('marta', self.bit, pagador=pagador)
        salvar_leitura('bit', [acesso('ana'), acesso('marta')])
        self.assertEqual(self.tipos(), set())

    def test_ausente_so_avisa_com_painel_lido(self):
        self.lista('sumiu', self.warez)
        salvar_leitura('bit', [acesso('outra')])
        self.assertNotIn(('fora_paineis', 'sumiu'), self.tipos())
        salvar_leitura('knewcms', [acesso('outra2')])
        self.assertIn(('fora_paineis', 'sumiu'), self.tipos())

    def test_lista_sem_servidor_exige_os_dois_paineis(self):
        ListaCanais.objects.create(cliente=self.cliente, nome='x', usuario='sem', senha='s1')
        salvar_leitura('bit', [acesso('a')])
        self.assertNotIn(('fora_paineis', 'sem'), self.tipos())
        salvar_leitura('knewcms', [acesso('b')])
        self.assertIn(('fora_paineis', 'sem'), self.tipos())

    def test_servidor_sem_painel_fica_como_nao_conferido(self):
        self.lista('outro', self.outro)
        salvar_leitura('bit', [acesso('a')])
        salvar_leitura('knewcms', [acesso('b')])
        achados, sem_painel = calcular_divergencias()
        self.assertNotIn('outro', [a.usuario for a in achados])
        self.assertEqual([l.usuario for l in sem_painel], ['outro'])

    def test_dados_diferentes(self):
        self.lista('casa', self.bit, num_telas=2)
        salvar_leitura('bit', [acesso('casa', senha='trocada', telas=1, ativo=False)])
        tipos = self.tipos()
        self.assertIn(('senha', 'casa'), tipos)
        self.assertIn(('telas', 'casa'), tipos)
        self.assertIn(('bloqueada', 'casa'), tipos)

    def test_senha_diferente_lista_os_apps_e_nunca_mostra_a_senha(self):
        lista = self.lista('casa', self.bit, senha='senha-do-sistema')
        ListaApp.objects.create(lista=lista, app=AppIPTV.objects.create(nome='Smarters'))
        ListaApp.objects.create(lista=lista, app=AppIPTV.objects.create(nome='Clouddy'))
        salvar_leitura('bit', [acesso('casa', senha='senha-do-painel')])
        achado = [a for a in calcular_divergencias()[0] if a.tipo == 'senha'][0]
        self.assertIn('Smarters', achado.detalhe)
        self.assertIn('Clouddy', achado.detalhe)
        self.assertNotIn('senha-do', achado.descricao)
        self.assertNotIn('senha-do', achado.chave)

    def test_lixeira_vencida_e_inativa(self):
        self.lista('lixo', self.warez)
        self.lista('venceu', self.warez)
        self.lista('parada', self.warez, ativa=False)
        salvar_leitura('knewcms', [
            acesso('lixo', lixeira=True),
            acesso('venceu', validade=timezone.now() - timedelta(days=2)),
            acesso('parada'),
        ])
        tipos = self.tipos()
        self.assertIn(('lixeira', 'lixo'), tipos)
        self.assertIn(('vencida', 'venceu'), tipos)
        self.assertIn(('inativa', 'parada'), tipos)

    def test_fora_do_sistema_sugere_pela_observacao(self):
        self.lista('login-antigo', self.warez)
        salvar_leitura('knewcms', [acesso('novo', observacao='Carlos Prado')])
        achado = [a for a in calcular_divergencias()[0] if a.tipo == 'fora_sistema'][0]
        self.assertIn('Pode ser: Carlos Prado', achado.detalhe)

    def test_login_repetido(self):
        outro = Cliente.objects.create(nome='Nina', whatsapp='5551900000003')
        self.lista('tv1', self.bit)
        self.lista('tv1', self.bit, cliente=outro)
        salvar_leitura('bit', [acesso('tv1')])
        self.assertIn(('repetido', 'tv1'), self.tipos())

    def test_whatsapp_com_e_sem_ddi_nao_diverge(self):
        self.lista('casa', self.warez, em_teste=False)
        salvar_leitura('knewcms', [acesso('casa', whatsapp='51900000001')])
        self.assertNotIn(('whatsapp', 'casa'), self.tipos())

    def test_ignorar_some_da_contagem(self):
        self.lista('casa', self.bit)
        salvar_leitura('bit', [acesso('casa', senha='trocada')])
        self.assertEqual(contar_divergencias(), 1)
        item = montar_conferencia()['grupos'][3]['itens'][0]
        DivergenciaIgnorada.objects.create(chave=item.chave, descricao=item.descricao)
        conferencia = montar_conferencia()
        self.assertEqual(conferencia['total'], 0)
        self.assertEqual(len(conferencia['ignoradas']), 1)


class LeituraTests(Base):
    def test_nao_guarda_senha(self):
        importar_bit(1, [{'usuario': 'a', 'senha': 'segredo', 'estado': 'Ativa', 'telas': '2', 'validade': '10/12/2026 13:16'}])
        registro = AcessoPainel.objects.get(usuario='a')
        self.assertNotEqual(registro.senha_hash, 'segredo')
        self.assertEqual(registro.senha_hash, assinar_senha('segredo'))
        self.assertEqual(registro.telas, 2)
        self.assertEqual(timezone.localtime(registro.validade).strftime('%d/%m/%Y %H:%M'), '10/12/2026 13:16')

    def test_bit_incompleto_mantem_dados_anteriores(self):
        salvar_leitura('bit', [acesso('a')])
        with self.assertRaises(LeituraInvalida):
            importar_bit(2, [{'usuario': 'b'}])
        self.assertTrue(AcessoPainel.objects.filter(usuario='a').exists())
        self.assertFalse(LeituraPainel.objects.filter(painel='bit').first().sucesso)

    def test_queda_brusca_mantem_dados_anteriores(self):
        salvar_leitura('bit', [acesso(f'u{i}') for i in range(10)])
        with self.assertRaises(LeituraInvalida):
            salvar_leitura('bit', [acesso('u1')])
        self.assertEqual(AcessoPainel.objects.filter(painel='bit').count(), 10)

    def test_acesso_removido_do_painel_sai_da_foto(self):
        salvar_leitura('bit', [acesso('a'), acesso('b')])
        salvar_leitura('bit', [acesso('a')])
        self.assertFalse(AcessoPainel.objects.filter(usuario='b').exists())

    @override_settings(WWPANEL_API_TOKEN='token')
    def test_knewcms_le_paginas_testes_e_lixeira(self):
        def resposta(params):
            if params['is_trial'] == 0 and params['trash'] == 0:
                return {'items': [{'id': params['page'], 'username': f"p{params['page']}", 'password': 'x', 'status': 1, 'exp_date': '2027-02-01T02:59:59.999Z', 'max_connections': 2, 'whatsapp': None, 'notes': None}], 'pagesQuantity': 2}
            if params['is_trial'] == 0 and params['trash'] == 1:
                return {'items': [{'id': 9, 'username': 'lixo', 'password': 'x', 'status': 1}], 'pagesQuantity': 1}
            if params['is_trial'] == 1 and params['trash'] == 0:
                return {'items': [{'id': 8, 'username': 'teste', 'password': 'x', 'status': 1}], 'pagesQuantity': 1}
            return {'items': [], 'pagesQuantity': 0}

        with mock.patch.object(leitura, '_knewcms_get', side_effect=resposta) as chamada:
            leitura.ler_knewcms()
        self.assertEqual(chamada.call_count, 5)
        self.assertEqual(AcessoPainel.objects.filter(painel='knewcms').count(), 4)
        self.assertTrue(AcessoPainel.objects.get(usuario='lixo').lixeira)
        self.assertTrue(AcessoPainel.objects.get(usuario='teste').teste)
        self.assertEqual(AcessoPainel.objects.get(usuario='p1').telas, 2)

    @override_settings(WWPANEL_API_TOKEN='')
    def test_knewcms_sem_token_falha_sem_chamar_api(self):
        with mock.patch.object(leitura, '_knewcms_get') as chamada:
            with self.assertRaises(LeituraInvalida):
                leitura.ler_knewcms()
        chamada.assert_not_called()


class VinculoTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_user('ramon', password='x'))

    def test_login_igual_vincula_sozinho_e_troca_de_login_vira_um_aviso(self):
        self.lista('antigo', self.warez)
        salvar_leitura('knewcms', [acesso('antigo', painel_id='77')])
        self.assertEqual(VinculoPainel.objects.get().painel_id, '77')
        salvar_leitura('knewcms', [acesso('novo', painel_id='77')])
        achados = calcular_divergencias()[0]
        self.assertEqual([a.tipo for a in achados], ['login'])
        self.assertIn('Login no sistema: antigo · no painel: novo', achados[0].detalhe)

    def test_nao_vincula_sozinho_com_login_repetido_ou_outro_painel(self):
        outro = Cliente.objects.create(nome='Nina', whatsapp='5551900000003')
        self.lista('rep', self.warez)
        self.lista('rep', self.warez, cliente=outro)
        self.lista('dobit', self.bit)
        salvar_leitura('knewcms', [acesso('rep', painel_id='1'), acesso('dobit', painel_id='2')])
        self.assertFalse(VinculoPainel.objects.exists())

    def test_vincular_na_tela_nao_altera_a_lista(self):
        lista = self.lista('antigo', self.warez, senha='s1')
        salvar_leitura('knewcms', [acesso('novo', painel_id='77', observacao='Carlos Prado')])
        item = [a for a in calcular_divergencias()[0] if a.tipo == 'fora_sistema'][0]
        self.assertEqual(item.sugerida_id, lista.pk)
        self.assertEqual(item.candidatas[0][0], lista.pk)
        self.assertContains(self.client.get(reverse('conferencia:painel')), 'Vincular')
        self.client.post(reverse('conferencia:vincular'), {'acesso_id': item.acesso_id, 'lista_id': lista.pk})
        lista.refresh_from_db()
        self.assertEqual(lista.usuario, 'antigo')
        self.assertEqual([a.tipo for a in calcular_divergencias()[0]], ['login'])

    def test_corrigir_o_login_na_lista_encerra_o_aviso(self):
        lista = self.lista('antigo', self.warez)
        salvar_leitura('knewcms', [acesso('antigo', painel_id='77')])
        salvar_leitura('knewcms', [acesso('novo', painel_id='77')])
        lista.usuario = 'novo'
        lista.save()
        self.assertEqual(calcular_divergencias()[0], [])

    def test_vinculo_recusa_duplicidade(self):
        a = self.lista('a', self.warez)
        b = self.lista('b', self.warez)
        salvar_leitura('knewcms', [acesso('a', painel_id='1'), acesso('x', painel_id='2'), acesso('y', painel_id='3')])
        x = AcessoPainel.objects.get(usuario='x')
        self.client.post(reverse('conferencia:vincular'), {'acesso_id': x.pk, 'lista_id': a.pk})
        self.assertEqual(VinculoPainel.objects.get(lista=a).painel_id, '1')
        self.client.post(reverse('conferencia:vincular'), {'acesso_id': x.pk, 'lista_id': b.pk})
        self.client.post(reverse('conferencia:vincular'), {'acesso_id': AcessoPainel.objects.get(usuario='y').pk, 'lista_id': b.pk})
        self.assertEqual(VinculoPainel.objects.get(lista=b).painel_id, '2')

    def test_desvincular_volta_a_comparar_pelo_login(self):
        self.lista('antigo', self.warez)
        salvar_leitura('knewcms', [acesso('antigo', painel_id='77')])
        salvar_leitura('knewcms', [acesso('novo', painel_id='77')])
        vinculo = VinculoPainel.objects.get()
        self.client.post(reverse('conferencia:desvincular', args=[vinculo.pk]))
        tipos = {a.tipo for a in calcular_divergencias()[0]}
        self.assertEqual(tipos, {'fora_paineis', 'fora_sistema'})

    def test_acesso_vinculado_que_saiu_avisa(self):
        self.lista('casa', self.warez)
        salvar_leitura('knewcms', [acesso('casa', painel_id='1'), acesso('outro', painel_id='2')])
        salvar_leitura('knewcms', [acesso('outro', painel_id='2')])
        achado = [a for a in calcular_divergencias()[0] if a.tipo == 'fora_paineis'][0]
        self.assertIn('o acesso vinculado saiu do painel', achado.detalhe)

    def test_bit_usa_o_id_e_le_os_campos_do_painel(self):
        self.lista('um', self.bit)
        importar_bit(2, [
            {'id': 'uuid-1', 'usuario': 'um', 'senha': 's1', 'estado': 'ACTIVE', 'telas': 2, 'validade': '2026-12-10T16:16:00.000Z', 'whatsapp': '5551900000001', 'observacao': 'Sala'},
            {'id': 'uuid-2', 'usuario': 'dois', 'senha': 's2', 'estado': 'DISABLED', 'telas': 1, 'validade': '2026-12-10T16:16:00.000Z', 'whatsapp': None, 'observacao': None},
        ])
        um = AcessoPainel.objects.get(usuario='um')
        self.assertEqual(um.painel_id, 'uuid-1')
        self.assertTrue(um.ativo)
        self.assertEqual(um.telas, 2)
        self.assertEqual(um.observacao, 'Sala')
        self.assertEqual(timezone.localtime(um.validade).strftime('%d/%m/%Y %H:%M'), '10/12/2026 13:16')
        self.assertFalse(AcessoPainel.objects.get(usuario='dois').ativo)
        self.assertEqual(VinculoPainel.objects.get().painel_id, 'uuid-1')

    def test_troca_de_usuario_no_bit_mantem_o_vinculo(self):
        self.lista('antigo', self.bit)
        linha = {'id': 'uuid-1', 'senha': 's1', 'estado': 'ACTIVE', 'telas': 1, 'validade': '2027-12-10T16:16:00.000Z'}
        importar_bit(1, [{**linha, 'usuario': 'antigo'}])
        importar_bit(1, [{**linha, 'usuario': 'novo'}])
        achados = calcular_divergencias()[0]
        self.assertEqual([a.tipo for a in achados], ['login'])

    def test_favorito_antigo_sem_criacao_continua_comparando_por_login(self):
        self.lista('um', self.bit)
        importar_bit(1, [{'usuario': 'um', 'senha': 's1', 'estado': 'Ativa', 'telas': '1', 'validade': '10/12/2026 13:16'}])
        self.assertFalse(VinculoPainel.objects.exists())
        self.assertEqual(calcular_divergencias()[0], [])

    def test_contagem_do_menu_muda_com_novo_vinculo(self):
        lista = self.lista('antigo', self.warez)
        salvar_leitura('knewcms', [acesso('novo', painel_id='77')])
        self.assertEqual(contar_divergencias(), 2)
        VinculoPainel.objects.create(lista=lista, painel='knewcms', painel_id='77')
        self.assertEqual(contar_divergencias(), 1)


class FrequenciaTests(Base):
    def registrar_leitura(self, horas_atras):
        registro = LeituraPainel.objects.create(painel='knewcms', total=1)
        LeituraPainel.objects.filter(pk=registro.pk).update(lida_em=timezone.now() - timedelta(hours=horas_atras))

    def test_padrao_duas_vezes_ao_dia(self):
        self.assertEqual(ConfiguracaoConferencia.atual().intervalo_horas, 12)

    def test_sem_leitura_anterior_le(self):
        self.assertTrue(knewcms_na_hora())

    def test_respeita_o_intervalo(self):
        self.registrar_leitura(5)
        self.assertFalse(knewcms_na_hora())
        LeituraPainel.objects.all().delete()
        self.registrar_leitura(12)
        self.assertTrue(knewcms_na_hora())

    def test_folga_nao_pula_o_horario(self):
        self.registrar_leitura(11.9)
        self.assertTrue(knewcms_na_hora())

    def test_so_manual_nunca_le_sozinho(self):
        ConfiguracaoConferencia.objects.update_or_create(pk=1, defaults={'intervalo_horas': 0})
        self.assertFalse(knewcms_na_hora())

    def test_falha_nao_conta_como_leitura(self):
        self.registrar_leitura(13)
        LeituraPainel.objects.create(painel='knewcms', sucesso=False, erro='x')
        self.assertTrue(knewcms_na_hora())

    def test_tela_salva_e_recusa_valor_invalido(self):
        self.client.force_login(User.objects.create_user('ramon', password='x'))
        self.client.post(reverse('conferencia:salvar_frequencia'), {'intervalo_horas': '24'})
        self.assertEqual(ConfiguracaoConferencia.atual().intervalo_horas, 24)
        self.client.post(reverse('conferencia:salvar_frequencia'), {'intervalo_horas': '1'})
        self.assertEqual(ConfiguracaoConferencia.atual().intervalo_horas, 24)
        self.assertContains(self.client.get(reverse('conferencia:painel')), '1 vez ao dia')


class TelasTests(Base):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('ramon', password='x')

    def test_exige_login(self):
        self.assertEqual(self.client.get(reverse('conferencia:painel')).status_code, 302)
        resposta = self.client.post(reverse('conferencia:importar_bit'), '{}', content_type='application/json')
        self.assertEqual(resposta.status_code, 302)

    def test_painel_e_menu_mostram_divergencia(self):
        self.lista('casa', self.bit)
        salvar_leitura('bit', [acesso('casa', senha='trocada')])
        self.client.force_login(self.user)
        resposta = self.client.get(reverse('conferencia:painel'))
        self.assertContains(resposta, 'A senha do painel é diferente da salva')
        self.assertContains(resposta, 'Conferir BIT')
        self.assertEqual(resposta.context['conferencia_total'], 1)

    def test_so_a_aba_que_recebe_o_bit_libera_a_comunicacao_entre_abas(self):
        self.client.force_login(self.user)
        resposta = self.client.get(reverse('conferencia:receber_bit'))
        self.assertEqual(resposta['Cross-Origin-Opener-Policy'], 'unsafe-none')
        resposta = self.client.get(reverse('conferencia:painel'))
        self.assertEqual(resposta['Cross-Origin-Opener-Policy'], 'same-origin')

    def test_importa_bit_por_post(self):
        self.client.force_login(self.user)
        corpo = {'total': 1, 'linhas': [{'usuario': 'a', 'senha': 'x', 'estado': 'Ativa', 'telas': '1', 'validade': '10/12/2026 13:16'}]}
        resposta = self.client.post(reverse('conferencia:importar_bit'), corpo, content_type='application/json')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'total': 1})

    def test_importa_bit_invalido_responde_erro(self):
        self.client.force_login(self.user)
        resposta = self.client.post(reverse('conferencia:importar_bit'), 'nao-json', content_type='application/json')
        self.assertEqual(resposta.status_code, 400)

    def test_bookmarklet_so_envia_para_a_origem_do_sistema(self):
        codigo = gerar_bookmarklet('https://tv.rdmon.com')
        self.assertTrue(codigo.startswith('javascript:'))
        self.assertIn('"https://tv.rdmon.com"', codigo)
        self.assertNotIn('\n', codigo)
