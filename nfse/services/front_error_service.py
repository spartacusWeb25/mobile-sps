from nfse.exceptions import NfseClientError


class FrontErrorService:
    @staticmethod
    def to_message(exc: Exception, fallback: str) -> str:
        if isinstance(exc, NfseClientError):
            resposta = exc.resposta or {}
            if isinstance(resposta, dict):
                mensagem = resposta.get('message') or resposta.get('mensagem')
                codigo = resposta.get('code')
                if mensagem and codigo:
                    return f"{mensagem} (código: {codigo})"
                if mensagem:
                    return str(mensagem)
        text = str(exc).strip()
        return text or fallback
