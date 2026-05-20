# produtos/services/produto_marketplace_service.py

class ProdutoMarketplaceService:
    PREFIXO_ML = "Sps"

    def __init__(self, db_alias="default"):
        self.db_alias = db_alias

    def gerar_sku_mercado_livre(self, produto):
        return f"{self.PREFIXO_ML}-{produto.prod_codi}"

    def gerar_codigo_mercado_livre(self, produto):
        if produto.prod_codi_merc_livr:
            return produto.prod_codi_merc_livr

        produto.prod_codi_merc_livr = self.gerar_sku_mercado_livre(produto)
        produto.save(
            using=self.db_alias,
            update_fields=["prod_codi_merc_livr"],
        )

        return produto.prod_codi_merc_livr