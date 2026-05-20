import unittest

from nfse.services.calculo_service import CalculoNfseService


class CalculoNfseServiceTests(unittest.TestCase):
    def test_calcula_iss_quando_aliquota_informada(self):
        data = {'valor_servico': '100.00', 'aliquota_iss': '5.0000'}
        out = CalculoNfseService.aplicar(data)
        self.assertEqual(str(out['valor_iss']), '5.00')
        self.assertEqual(str(out['valor_liquido']), '95.00')

    def test_calcula_aliquota_quando_iss_informado(self):
        data = {'valor_servico': '200.00', 'valor_iss': '6.00'}
        out = CalculoNfseService.aplicar(data)
        self.assertEqual(str(out['aliquota_iss']), '3.0000')

    def test_calcula_com_deducao_desconto_e_retencoes(self):
        data = {
            'valor_servico': '1000.00',
            'valor_deducao': '100.00',
            'valor_desconto': '50.00',
            'aliquota_iss': '5.0000',
            'valor_inss': '10.00',
            'valor_irrf': '20.00',
            'valor_csll': '5.00',
            'valor_cofins': '7.00',
            'valor_pis': '3.00',
        }
        out = CalculoNfseService.aplicar(data)
        self.assertEqual(str(out['valor_iss']), '45.00')
        self.assertEqual(str(out['valor_liquido']), '760.00')


if __name__ == '__main__':
    unittest.main()
