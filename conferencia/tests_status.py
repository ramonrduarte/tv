from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from . import escrita, leitura, status
from .leitura import LeituraInvalida
from .models import LeituraPainel
from .operacoes import executar_renovacao
from .tests_operacoes import Base


class RespostaIP:
    def __init__(self, ip):
        self.ip = ip

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.ip.encode()


@override_settings(CONSULTAS_NA_TELA=True)
class SituacaoBitTests(Base):
    def setUp(self):
        super().setUp()
        cache.clear()

    def ler_bit(self, ip, falha=None):
        cache.delete(status.CHAVE_IP)
        efeito = falha or (lambda *a: {'data': [{'username': 'b1', 'password': 's1', 'status': 'ACTIVE'}], 'pagination': {'pages': 1}})
        with mock.patch.object(status.urllib.request, 'urlopen', return_value=RespostaIP(ip)), \
             mock.patch.object(leitura, '_bit_get', side_effect=efeito):
            try:
                leitura.ler_painel('bit')
            except LeituraInvalida:
                pass

    def test_guarda_o_ip_de_cada_leitura(self):
        self.ler_bit('191.0.0.1')
        self.assertEqual(LeituraPainel.objects.filter(painel='bit').first().ip_saida, '191.0.0.1')

    def test_avisa_quando_o_ip_muda(self):
        self.ler_bit('191.0.0.1')
        cache.set(status.CHAVE_IP, '200.0.0.9')
        with mock.patch.object(escrita, '_bit', return_value={'credits': 70}):
            situacao = status.situacao_bit()
        self.assertTrue(situacao['ip_mudou'])
        self.assertEqual((situacao['ip'], situacao['ip_autorizado'], situacao['creditos']), ('200.0.0.9', '191.0.0.1', 70))

    def test_avisa_quando_o_bit_recusa_por_ip(self):
        self.ler_bit('191.0.0.1', falha=LeituraInvalida('A API do BIT respondeu com erro 403: IP_NOT_ALLOWED.'))
        with mock.patch.object(escrita, '_bit', return_value={'credits': 70}):
            situacao = status.situacao_bit()
        self.assertTrue(situacao['recusa_ip'])
        self.assertEqual(LeituraPainel.objects.first().ip_saida, '191.0.0.1')

    def test_creditos_ficam_em_cache_e_renovacao_atualiza(self):
        with mock.patch.object(escrita, '_bit', return_value={'credits': 77}) as bit:
            self.assertEqual(status.creditos_bit(), 77)
            self.assertEqual(status.creditos_bit(), 77)
        self.assertEqual(bit.call_count, 1)
        with mock.patch.object(escrita, '_bit', return_value={'line': {}, 'credits': 76}):
            executar_renovacao([self.l_bit.pk], 1, {self.l_bit.pk: 'p'}, self.user)
        self.assertEqual(status.creditos_bit(), 76)

    def test_telas_mostram_creditos_e_ip(self):
        self.ler_bit('191.0.0.1')
        cache.set(status.CHAVE_CREDITOS, 55)
        for url in (reverse('conferencia:painel'), reverse('dashboard')):
            resposta = self.client.get(url)
            self.assertContains(resposta, 'Créditos: <strong>55</strong>')
            self.assertContains(resposta, '191.0.0.1')
            self.assertContains(resposta, 'IP autorizado')

    @override_settings(BIT_API_TOKEN='')
    def test_sem_chave_do_bit_nada_aparece(self):
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Painel BIT')


class SemRedeNosTestesTests(Base):
    def test_telas_nao_consultam_rede_nos_testes(self):
        with mock.patch.object(status.urllib.request, 'urlopen') as rede, mock.patch.object(escrita, '_bit') as bit:
            self.client.get(reverse('conferencia:painel'))
            self.client.get(reverse('dashboard'))
        rede.assert_not_called()
        bit.assert_not_called()
