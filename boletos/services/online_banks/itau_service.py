import base64

import requests

from .base import BaseOAuthBoletoService, OnlineBankAPIError


class ItauCobrancaService(BaseOAuthBoletoService):
    bank_code = 'ITAU'
    bank_name = 'Itaú'

    def default_token_path(self):
        return '/oauth/token'

    def default_boletos_path(self):
        return '/v1/boletos'

    def obter_pdf_boleto(self, nosso_numero, linha_digitavel=None):
        token = self._token()
        headers_pdf = dict(self._headers(token))
        headers_pdf['Accept'] = 'application/pdf'
        headers_json = dict(headers_pdf)
        headers_json['Accept'] = 'application/json'

        def _deep_get(obj, path):
            cur = obj
            for part in str(path).split('.'):
                if cur is None:
                    return None
                if isinstance(cur, (list, tuple)):
                    if not part.isdigit():
                        return None
                    idx = int(part)
                    if idx < 0 or idx >= len(cur):
                        return None
                    cur = cur[idx]
                    continue
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(part)
            return cur

        def _extract(data, *paths):
            for p in paths:
                v = _deep_get(data, p)
                if v:
                    return v
            return None

        ld = ''.join(ch for ch in str(linha_digitavel or '').strip() if ch.isdigit())
        candidates = []
        if ld:
            candidates.append((f"{self.boletos_url()}/pdf", {'linhaDigitavel': ld}, headers_json))
            candidates.append((f"{self.boletos_url()}/impressao", {'linhaDigitavel': ld}, headers_json))

        for nn in self._nosso_numero_candidates(nosso_numero):
            candidates.append((f"{self.boletos_url()}/{nn}/pdf", None, headers_pdf))
            candidates.append((f"{self.boletos_url()}/{nn}/impressao", None, headers_pdf))
            candidates.append((f"{self.boletos_url()}/pdf", {'nossoNumero': nn}, headers_json))
            candidates.append((f"{self.boletos_url()}/impressao", {'nossoNumero': nn}, headers_json))

        errors = []
        for url, params, headers in candidates:
            r = self._request('GET', url, params=params, headers=headers, timeout=45)
            if r.status_code >= 400:
                errors.append(f'GET {url} -> {r.status_code}')
                continue

            content = r.content or b''
            if content.startswith(b'%PDF'):
                return content

            ct = (r.headers.get('Content-Type') or '').lower()
            if 'application/pdf' in ct and content:
                return content

            try:
                data = r.json() if (r.text or '').strip() else {}
            except Exception:
                data = {}

            if isinstance(data, dict):
                b64 = _extract(data, 'pdf', 'conteudoPdf', 'conteudoPDF', 'content')
                if isinstance(b64, str) and b64.strip():
                    try:
                        decoded = base64.b64decode(b64, validate=False)
                    except Exception:
                        decoded = b''
                    if decoded.startswith(b'%PDF'):
                        return decoded

                link = _extract(data, 'linkBoleto', 'urlBoleto', 'boletoUrl', 'links.0.href')
                if isinstance(link, str) and link.lower().startswith(('http://', 'https://')):
                    r2 = requests.get(link, headers={'Accept': 'application/pdf'}, timeout=45)
                    if r2.status_code < 400 and (r2.content or b'').startswith(b'%PDF'):
                        return r2.content
                    errors.append(f'GET {link} -> {r2.status_code}')
                    continue

        raise OnlineBankAPIError('Falha ao obter PDF do boleto (Itaú): ' + ' | '.join(errors))
