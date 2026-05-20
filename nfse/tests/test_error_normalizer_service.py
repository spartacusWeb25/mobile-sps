import unittest

from nfse.services.error_normalizer_service import ErrorNormalizerService


class ErrorNormalizerServiceTests(unittest.TestCase):
    def test_normalize_elotech_with_known_code(self):
        result = ErrorNormalizerService.normalize_elotech(code='E13', message='Documento inválido')
        self.assertEqual(result['provider'], 'elotech')
        self.assertEqual(result['code'], 'E13')
        self.assertIn('CPF/CNPJ', result['message'])
        self.assertEqual(result['raw_message'], 'Documento inválido')

    def test_normalize_elotech_without_code(self):
        result = ErrorNormalizerService.normalize_elotech(message='Falha de comunicação')
        self.assertEqual(result['message'], 'Falha de comunicação')
        self.assertIsNone(result['code'])

    def test_extract_code_from_message(self):
        result = ErrorNormalizerService.normalize_elotech(message='Erro E13: documento inválido')
        self.assertEqual(result['code'], 'E13')
        self.assertIn('CPF/CNPJ', result['message'])


if __name__ == '__main__':
    unittest.main()
