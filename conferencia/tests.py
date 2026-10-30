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
from .leitura import LeituraInvalida, assinar_senha, importar_bit, salvar_leitura
from .models import AcessoPainel, DivergenciaIgnorada, LeituraPainel
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
