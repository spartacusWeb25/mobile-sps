from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from boletos.services.online_banks.bb_service import BancoBrasilCobrancaService


class _Resp:
    def __init__(self, status=200, json_data=None, text=''):
        self.status_code = status
        self._json = json_data if json_data is not None else {}
        self.text = text if text else ('{}' if json_data is not None else '')

    def json(self):
        return self._json


class BancoBrasilCobrancaServiceTests(SimpleTestCase):
    def _carteira(self):
        return SimpleNamespace(
            cart_webs_ssl_lib='sandbox',
            cart_webs_clie_id='client-id',
            cart_webs_clie_secr='client-secret',
            cart_webs_user_key='app-key',
            cart_webs_scop='cobrancas.boletos-info',
            cart_conv='1234567',
        )

    @patch('boletos.services.online_banks.bb_service.requests.post')
    @patch('boletos.services.online_banks.bb_service.requests.request')
    def test_registrar(self, mock_request, mock_post_token):
        mock_post_token.return_value = _Resp(json_data={'access_token': 'tok'})
        mock_request.return_value = _Resp(json_data={'ok': True})

        service = BancoBrasilCobrancaService(self._carteira())
        data = service.registrar_boleto({'campo': 'valor'})
        self.assertTrue(data.get('ok'))

    @patch('boletos.services.online_banks.bb_service.requests.post')
    @patch('boletos.services.online_banks.bb_service.requests.request')
    def test_consultar_tenta_multiplos_ids(self, mock_request, mock_post_token):
        mock_post_token.return_value = _Resp(json_data={'access_token': 'tok'})

        def _side_effect(method, url, **kwargs):
            if url.endswith('/boletos/000123'):
                return _Resp(status=404, text='')
            return _Resp(json_data={'linhaDigitavel': '123', 'numero': 'ok'})

        mock_request.side_effect = _side_effect

        service = BancoBrasilCobrancaService(self._carteira())
        data = service.consultar_boleto('000123')
        self.assertEqual(data.get('numero'), 'ok')

    @patch('boletos.services.online_banks.bb_service.requests.post')
    @patch('boletos.services.online_banks.bb_service.requests.request')
    def test_baixar(self, mock_request, mock_post_token):
        mock_post_token.return_value = _Resp(json_data={'access_token': 'tok'})

        def _side_effect(method, url, **kwargs):
            if url.endswith('/boletos/000123/baixar'):
                return _Resp(status=404, text='')
            return _Resp(json_data={'ok': True})

        mock_request.side_effect = _side_effect

        service = BancoBrasilCobrancaService(self._carteira())
        data = service.baixar_boleto('000123', payload={'codigoBaixa': 1})
        self.assertTrue(data.get('ok'))

    @patch('boletos.services.online_banks.bb_service.requests.post')
    @patch('boletos.services.online_banks.bb_service.requests.request')
    def test_alterar_vencimento_monta_payload_bb(self, mock_request, mock_post_token):
        mock_post_token.return_value = _Resp(json_data={'access_token': 'tok'})

        def _side_effect(method, url, **kwargs):
            if url.endswith('/boletos/000123'):
                return _Resp(status=404, text='')
            return _Resp(json_data={'ok': True})

        mock_request.side_effect = _side_effect

        service = BancoBrasilCobrancaService(self._carteira())
        data = service.alterar_boleto('000123', payload={'dataVencimento': '2026-05-01'})
        self.assertTrue(data.get('ok'))

