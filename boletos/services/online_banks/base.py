import os
import logging
import requests
from .wallet_config import validate_online_wallet_config


class OnlineBankAPIError(Exception):
    pass


class BaseOAuthBoletoService:
    """Base hexagonal para APIs de boleto com OAuth client_credentials."""

    bank_code = None
    bank_name = None

    def __init__(self, carteira):
        self.carteira = carteira
        self.logger = logging.getLogger(self.__class__.__name__)

    def _clean(self, value):
        return str(value or '').strip()

    def _env(self, name):
        return self._clean(os.getenv(name))

    def _digits(self, value):
        return ''.join(ch for ch in self._clean(value) if ch.isdigit())

    def _nosso_numero_candidates(self, nosso_numero):
        raw = self._clean(nosso_numero)
        digits = self._digits(raw)
        if not digits:
            return [raw] if raw else []
        seen = set()
        candidates = []
        for v in (digits, digits.lstrip('0') or '0'):
            if v and v not in seen:
                seen.add(v)
                candidates.append(v)
        for size in (9, 10, 15, 20):
            v = digits.zfill(size)
            if v not in seen:
                seen.add(v)
                candidates.append(v)
        return candidates

    def _base_url(self):
        configured = self._clean(getattr(self.carteira, 'cart_webs_ssl_lib', ''))
        if configured.startswith('http'):
            return configured.rstrip('/')
        env_base = self._env(f'{self.bank_code}_BASE_URL')
        if env_base:
            return env_base.rstrip('/')
        raise OnlineBankAPIError(f'URL base não configurada para {self.bank_name}.')

    def token_url(self):
        custom = self._env(f'{self.bank_code}_TOKEN_URL')
        if custom:
            return custom
        return f'{self._base_url()}{self.default_token_path()}'

    def boletos_url(self):
        custom = self._env(f'{self.bank_code}_BOLETOS_URL')
        if custom:
            return custom.rstrip('/')
        return f'{self._base_url()}{self.default_boletos_path()}'

    def default_token_path(self):
        raise NotImplementedError

    def default_boletos_path(self):
        raise NotImplementedError

    def _request(self, method, url, *, headers=None, params=None, data=None, json=None, auth=None, timeout=30):
        try:
            return requests.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                json=json,
                auth=auth,
                timeout=timeout,
            )
        except Exception as ex:
            raise OnlineBankAPIError(f'Falha na requisição {self.bank_name}: {type(ex).__name__}')

    def _token(self):
        try:
            cfg = validate_online_wallet_config(self.carteira, self.bank_name)
        except ValueError as exc:
            raise OnlineBankAPIError(str(exc))
        client_id = cfg['client_id']
        client_secret = cfg['client_secret']
        scope = cfg['scope']
        api_key = cfg['api_key']

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        if api_key:
            headers['x-api-key'] = api_key

        data = {'grant_type': 'client_credentials'}
        if scope:
            data['scope'] = scope

        r = self._request(
            'POST',
            self.token_url(),
            data=data,
            headers=headers,
            auth=(client_id, client_secret),
            timeout=30,
        )
        if r.status_code >= 400:
            raise OnlineBankAPIError(f'Erro ao obter token {self.bank_name}: HTTP {r.status_code} - {r.text}')

        token = (r.json() or {}).get('access_token')
        if not token:
            raise OnlineBankAPIError(f'Resposta sem access_token ({self.bank_name}).')
        return token

    def _headers(self, token):
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        api_key = self._clean(getattr(self.carteira, 'cart_webs_user_key', ''))
        if api_key:
            headers['x-api-key'] = api_key
        return headers

    def registrar_boleto(self, payload):
        token = self._token()
        r = self._request(
            'POST',
            self.boletos_url(),
            json=payload,
            headers=self._headers(token),
            timeout=45,
        )
        if r.status_code >= 400:
            raise OnlineBankAPIError(f'Erro ao registrar boleto ({self.bank_name}): HTTP {r.status_code} - {r.text}')
        return r.json() if r.text else {'ok': True}

    def consultar_boleto(self, nosso_numero):
        token = self._token()
        headers = self._headers(token)

        errors = []
        for nn in self._nosso_numero_candidates(nosso_numero):
            url_list = self.boletos_url()
            r = self._request('GET', url_list, params={'nossoNumero': nn}, headers=headers, timeout=30)
            if r.status_code < 400:
                data = r.json() if r.text else {}
                if isinstance(data, list) and data:
                    return data[0]
                if isinstance(data, dict) and data:
                    return data
            else:
                if r.status_code not in (400, 404, 405, 422):
                    raise OnlineBankAPIError(
                        f'Erro ao consultar boleto ({self.bank_name}): HTTP {r.status_code} - {r.text}'
                    )
                errors.append(f'GET /boletos?nossoNumero={nn} -> {r.status_code}')

            url_one = f"{self.boletos_url()}/{nn}"
            r = self._request('GET', url_one, headers=headers, timeout=30)
            if r.status_code < 400:
                data = r.json() if r.text else {}
                if isinstance(data, list) and data:
                    return data[0]
                return data
            if r.status_code == 404:
                errors.append(f'GET /boletos/{nn} -> 404')
                continue
            raise OnlineBankAPIError(f'Erro ao consultar boleto ({self.bank_name}): HTTP {r.status_code} - {r.text}')

        raise OnlineBankAPIError(f'Boleto não encontrado ({self.bank_name}). Tentativas: {", ".join(errors) or "sem_candidatos"}')

    def baixar_boleto(self, nosso_numero, payload=None):
        token = self._token()
        return self._baixar_boleto_com_token(token, nosso_numero, payload=payload)

    def _baixar_boleto_com_token(self, token, nosso_numero, payload=None):
        headers = self._headers(token)
        errors = []
        for nn in self._nosso_numero_candidates(nosso_numero):
            candidates = [
                ('PATCH', f"{self.boletos_url()}/{nn}/baixa", None),
                ('POST', f"{self.boletos_url()}/{nn}/baixa", None),
                ('PATCH', f"{self.boletos_url()}/{nn}/pedido-baixa", None),
                ('POST', f"{self.boletos_url()}/{nn}/pedido-baixa", None),
                ('PATCH', f"{self.boletos_url()}/baixa", {'nossoNumero': nn}),
                ('POST', f"{self.boletos_url()}/baixa", {'nossoNumero': nn}),
            ]
            for method, url, params in candidates:
                r = self._request(method, url, params=params, json=payload or {}, headers=headers, timeout=30)
                if r.status_code < 400:
                    return r.json() if r.text else {'ok': True}
                if r.status_code not in (400, 404, 405, 422):
                    raise OnlineBankAPIError(f'Erro ao baixar boleto ({self.bank_name}): HTTP {r.status_code} - {r.text}')
                errors.append(f'{method} {url} -> {r.status_code}')
        raise OnlineBankAPIError(
            f'Falha ao baixar boleto ({self.bank_name}). Tentativas: {", ".join(errors) or "sem_candidatos"}'
        )

    def cancelar_boleto(self, nosso_numero, payload=None):
        """
        Padrão multi-banco:
        - tenta endpoint explícito de cancelamento
        - fallback para baixa para manter compatibilidade
        """
        token = self._token()
        headers = self._headers(token)
        errors = []
        for nn in self._nosso_numero_candidates(nosso_numero):
            candidates = [
                ('PATCH', f"{self.boletos_url()}/{nn}/cancelamento"),
                ('POST', f"{self.boletos_url()}/{nn}/cancelamento"),
                ('PATCH', f"{self.boletos_url()}/{nn}/cancelar"),
                ('POST', f"{self.boletos_url()}/{nn}/cancelar"),
            ]
            for method, url in candidates:
                r = self._request(method, url, json=payload or {}, headers=headers, timeout=30)
                if r.status_code < 400:
                    return r.json() if r.text else {'ok': True}
                if r.status_code in (404, 405):
                    errors.append(f'{method} {url} -> {r.status_code}')
                    continue
                if r.status_code not in (400, 422):
                    raise OnlineBankAPIError(f'Erro ao cancelar boleto ({self.bank_name}): HTTP {r.status_code} - {r.text}')
                errors.append(f'{method} {url} -> {r.status_code}')

            try:
                return self._baixar_boleto_com_token(token, nn, payload=payload)
            except OnlineBankAPIError as exc:
                errors.append(str(exc))
                continue

        raise OnlineBankAPIError(
            f'Falha ao cancelar boleto ({self.bank_name}). Tentativas: {", ".join(errors) or "sem_candidatos"}'
        )

    def adiantar_boleto(self, nosso_numero, payload):
        return self.alterar_boleto(nosso_numero, payload=payload)

    def alterar_boleto(self, nosso_numero, payload):
        token = self._token()
        headers = self._headers(token)

        data = payload if isinstance(payload, dict) else {}
        data_vencimento = self._clean(
            data.get('dataVencimento')
            or data.get('novoVencimento')
            or data.get('vencimento')
        )
        if not data_vencimento:
            raise OnlineBankAPIError(f'Erro ao alterar boleto ({self.bank_name}): payload sem data de vencimento.')

        payload_candidates = [
            {'dataVencimento': data_vencimento},
            {'novoVencimento': data_vencimento},
            {'vencimento': data_vencimento},
            {'dadosVencimento': {'dataVencimento': data_vencimento}},
            {'alteracao': {'dataVencimento': data_vencimento}},
            data,
        ]

        errors = []
        for nn in self._nosso_numero_candidates(nosso_numero):
            endpoints = [
                ('PATCH', f"{self.boletos_url()}/{nn}/data-vencimento", None),
                ('PATCH', f"{self.boletos_url()}/{nn}/vencimento", None),
                ('PUT', f"{self.boletos_url()}/{nn}/vencimento", None),
                ('PATCH', f"{self.boletos_url()}/{nn}/alterar-vencimento", None),
                ('PUT', f"{self.boletos_url()}/{nn}/alterar-vencimento", None),
                ('PATCH', f"{self.boletos_url()}/{nn}", None),
                ('PUT', f"{self.boletos_url()}/{nn}", None),
                ('PATCH', f"{self.boletos_url()}", {'nossoNumero': nn}),
                ('PUT', f"{self.boletos_url()}", {'nossoNumero': nn}),
                ('PATCH', f"{self.boletos_url()}/vencimento", {'nossoNumero': nn}),
                ('PUT', f"{self.boletos_url()}/vencimento", {'nossoNumero': nn}),
            ]
            for method, url, params in endpoints:
                for body in payload_candidates:
                    r = self._request(method, url, params=params, json=body, headers=headers, timeout=30)
                    if r.status_code < 400:
                        return r.json() if r.text else {'ok': True}
                    if r.status_code not in (400, 404, 405, 422):
                        raise OnlineBankAPIError(f'Erro ao alterar boleto ({self.bank_name}): HTTP {r.status_code} - {r.text}')
                    errors.append(f'{method} {url} -> {r.status_code}')

        raise OnlineBankAPIError(
            f'Falha ao alterar boleto ({self.bank_name}). Tentativas: {", ".join(errors) or "sem_candidatos"}'
        )
