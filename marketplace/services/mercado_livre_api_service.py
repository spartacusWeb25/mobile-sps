import requests
import logging
from django.utils import timezone

from marketplace.models import MarketplaceContasMl

logger = logging.getLogger(__name__)


class MercadoLivreApiService:
    BASE_URL = "https://api.mercadolibre.com"

    def __init__(self, db_alias="default", empresa=None, filial=None):
        self.db_alias = db_alias
        self.empresa = empresa
        self.filial = filial

    def obter_conta(self):
        conta = (
            MarketplaceContasMl.objects.using(self.db_alias)
            .filter(
                ml_empr=self.empresa,
                ml_fili=self.filial,
            )
            .first()
        )

        if not conta:
            raise ValueError("Conta Mercado Livre não configurada para esta empresa/filial.")

        return conta

    def obter_headers(self):
        conta = self.obter_conta()

        return {
            "Authorization": f"Bearer {conta.ml_access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def request(self, method, endpoint, payload=None, params=None):
        url = f"{self.BASE_URL}{endpoint}"

        logger.debug(f"ML Request -> {method} {url} params={params} payload={payload}")

        response = requests.request(
            method=method,
            url=url,
            headers=self.obter_headers(),
            json=payload,
            params=params,
            timeout=30,
        )

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.status_code >= 400:
            logger.error(f"ML Response Error: status={response.status_code} body={data}")
            raise ValueError({
                "status_code": response.status_code,
                "erro": data,
            })

        logger.debug(f"ML Response OK: status={response.status_code} body={data}")

        return data

    def publicar_anuncio(self, payload):
        return self.request(
            method="POST",
            endpoint="/items",
            payload=payload,
        )

    def buscar_anuncio(self, item_id):
        return self.request(
            method="GET",
            endpoint=f"/items/{item_id}",
        )

    def atualizar_preco(self, item_id, preco):
        return self.request(
            method="PUT",
            endpoint=f"/items/{item_id}",
            payload={"price": float(preco)},
        )

    def atualizar_estoque(self, item_id, quantidade):
        return self.request(
            method="PUT",
            endpoint=f"/items/{item_id}",
            payload={"available_quantity": int(quantidade)},
        )

    def pausar_anuncio(self, item_id):
        return self.request(
            method="PUT",
            endpoint=f"/items/{item_id}",
            payload={"status": "paused"},
        )