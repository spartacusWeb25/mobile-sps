import requests
import os
from dotenv import load_dotenv

load_dotenv()

from marketplace.models import MarketplaceContasMl


class MercadoLivreTokenService:
    TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

    def __init__(self, db_alias="default"):
        self.db_alias = db_alias

    def renovar_token(self, empresa, filial):
        conta = (
            MarketplaceContasMl.objects.using(self.db_alias)
            .filter(ml_empr=empresa, ml_fili=filial)
            .first()
        )

        if not conta:
            raise ValueError("Conta Mercado Livre não encontrada.")

        payload = {
            "grant_type": "refresh_token",
            "client_id": os.getenv("ML_CLIENT_ID"),
            "client_secret": os.getenv("ML_CLIENT_SECRET"),
            "refresh_token": conta.ml_refresh_token,
        }

        try:
            response = requests.post(self.TOKEN_URL, data=payload, timeout=30)
        except requests.RequestException as e:
            raise ValueError(f"Erro ao renovar token: {e}")
        data = response.json()

        if response.status_code >= 400:
            raise ValueError(data)

        conta.ml_access_token = data["access_token"]
        conta.ml_refresh_token = data.get("refresh_token", conta.ml_refresh_token)
        conta.ml_expires_in = data.get("expires_in", 0)

        try:
            conta.save(
                using=self.db_alias,
                update_fields=[
                    "ml_access_token",
                    "ml_refresh_token",
                    "ml_expires_in",
                    "ml_updated_at",
                ],
            )
        except Exception as e:
            raise ValueError(f"Erro ao salvar token: {e}")

        return conta