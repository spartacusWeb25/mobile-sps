from marketplace.models import MarketplaceContasMl


class MarketplaceConfigService:
    def __init__(self, db_alias="default"):
        self.db_alias = db_alias

    def painel_configuracoes(self, empresa, filial):
        conta_ml = (
            MarketplaceContasMl.objects.using(self.db_alias)
            .filter(ml_empr=empresa, ml_fili=filial)
            .first()
        )

        return {
            "mercado_livre": {
                "nome": "Mercado Livre",
                "ativo": bool(conta_ml),
                "conta": conta_ml,
            },
            "shopee": {
                "nome": "Shopee",
                "ativo": False,
                "conta": None,
            },
        }