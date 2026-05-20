import re

class ErrorNormalizerService:
    """Normaliza erros de provedores de NFS-e para payload padronizado."""

    ELOTECH_CODE_MAP = {
        'E4': 'RPS já informado anteriormente para este prestador.',
        'E13': 'CPF/CNPJ do tomador inválido.',
        'E31': 'Inscrição municipal do prestador inválida ou não encontrada.',
        'E160': 'Alíquota ISS inválida para o serviço informado.',
    }

    @classmethod
    def normalize_elotech(cls, *, code=None, message=None, raw=None):
        code = (code or '').strip()
        message = (message or '').strip()

        if not code and message:
            match = re.search(r'\b(E\d{1,4})\b', message)
            if match:
                code = match.group(1)
        canonical = cls.ELOTECH_CODE_MAP.get(code)

        if not canonical and message:
            canonical = message
        if not canonical:
            canonical = 'Erro retornado pelo provedor ELOTECH.'

        return {
            'provider': 'elotech',
            'code': code or None,
            'message': canonical,
            'raw_message': message or None,
            'retryable': code in {'E500', 'E999'},
            'raw': raw,
        }
