from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from boletos.services.online_banks.itau_service import ItauCobrancaService


class _Resp:
    def __init__(self, status=200, json_data=None, text='', headers=None, content=None):
        self.status_code = status
        self._json = json_data if json_data is not None else {}
        self.text = text if text else ('{}' if json_data is not None else '')
        self.content = content if content is not None else b''
        self.headers = headers if headers is not None else ({'Content-Type': 'application/pdf'} if self.content else {})

    def json(self):
        return self._json


class ItauCobrancaServiceTests(SimpleTestCase):
    def _carteira(self):
        return SimpleNamespace(
            cart_webs_ssl_lib='https://pix-pj.itau.com',
            cart_webs_clie_id='client-id',
            cart_webs_clie_secr='client-secret',
            cart_webs_user_key='',
            cart_webs_scop='',
        )

    @patch('boletos.services.online_banks.base.requests.request')
    def test_registrar(self, mock_request):
        mock_request.side_effect = [
            _Resp(json_data={'access_token': 'tok'}),
            _Resp(json_data={'nossoNumero': '123'}),
        ]
        service = ItauCobrancaService(self._carteira())
        data = service.registrar_boleto({'valor': 10})
        self.assertEqual(data.get('nossoNumero'), '123')

    @patch('boletos.services.online_banks.base.requests.request')
    def test_consultar_prioriza_lista_quando_disponivel(self, mock_request):
        mock_request.side_effect = [
            _Resp(json_data={'access_token': 'tok'}),
            _Resp(json_data=[{'nossoNumero': 'abc'}]),
        ]
        service = ItauCobrancaService(self._carteira())
        data = service.consultar_boleto('abc')
        self.assertEqual(data.get('nossoNumero'), 'abc')

    @patch('boletos.services.online_banks.base.requests.request')
    def test_baixar(self, mock_request):
        mock_request.side_effect = [
            _Resp(json_data={'access_token': 'tok'}),
            _Resp(json_data={'ok': True}),
        ]
        service = ItauCobrancaService(self._carteira())
        data = service.baixar_boleto('123')
        self.assertTrue(data.get('ok'))

    @patch('boletos.services.online_banks.base.requests.request')
    def test_cancelar_faz_fallback_para_baixa_quando_nao_suporta_cancelamento(self, mock_request):
        mock_request.side_effect = [
            _Resp(json_data={'access_token': 'tok'}),
            _Resp(status=404, text='not found'),
            _Resp(json_data={'ok': True}),
        ]
        service = ItauCobrancaService(self._carteira())
        data = service.cancelar_boleto('123')
        self.assertTrue(data.get('ok'))

    @patch('boletos.services.online_banks.base.requests.request')
    def test_alterar_vencimento(self, mock_request):
        calls = {'n': 0}

        def _side_effect(method, url, **kwargs):
            if url.endswith('/oauth/token'):
                return _Resp(json_data={'access_token': 'tok'})
            calls['n'] += 1
            if calls['n'] == 1:
                return _Resp(status=404, text='not found')
            return _Resp(json_data={'ok': True})

        mock_request.side_effect = _side_effect
        service = ItauCobrancaService(self._carteira())
        data = service.alterar_boleto('123', payload={'dataVencimento': '2026-05-01'})
        self.assertTrue(data.get('ok'))

    @patch('boletos.services.online_banks.base.requests.request')
    def test_obter_pdf_boleto_retorna_pdf_bytes(self, mock_request):
        mock_request.side_effect = [
            _Resp(json_data={'access_token': 'tok'}),
            _Resp(content=b'%PDF-1.4 test'),
        ]
        service = ItauCobrancaService(self._carteira())
        pdf = service.obter_pdf_boleto('123')
        self.assertTrue((pdf or b'').startswith(b'%PDF'))

