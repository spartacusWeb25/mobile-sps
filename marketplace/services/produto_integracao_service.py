from django.db import transaction

from marketplace.models import MarketplaceProduto, MarketplaceAnuncio
from Produtos.models import Produtos, Tabelaprecos, SaldoProduto


class MarketplaceProdutoService:
    def __init__(self, db_alias="default"):
        self.db_alias = db_alias

    # ─── helpers privados ────────────────────────────────────────────────────

    def _buscar_preco(self, empresa, filial, produto_codigo):
        tabela = (
            Tabelaprecos.objects.using(self.db_alias)
            .filter(
                tabe_empr=empresa,
                tabe_fili=filial,
                tabe_prod=produto_codigo,
            )
            .first()
        )
        if not tabela:
            return None
        return tabela.tabe_prco or tabela.tabe_avis or tabela.tabe_apra

    def _buscar_estoque(self, empresa, filial, produto_codigo):
        saldo = (
            SaldoProduto.objects.using(self.db_alias)
            .filter(
                empresa=str(empresa),
                filial=str(filial),
                produto_codigo_id=produto_codigo,
            )
            .first()
        )
        if not saldo:
            return 0
        return saldo.saldo_estoque or 0

    # ─── listagem ────────────────────────────────────────────────────────────

    def listar_produtos_com_sku_ml(self, empresa, filial=None):
        produtos = list(
            Produtos.objects.using(self.db_alias)
            .filter(
                prod_empr=str(empresa),
                prod_codi_merc_livr__isnull=False,
            )
            .exclude(prod_codi_merc_livr="")
            .order_by("prod_nome")
        )

        codigos = [p.prod_codi for p in produtos]

        integracoes = list(
            MarketplaceProduto.objects.using(self.db_alias).filter(
                mark_empr=empresa,
                mark_fili=filial,
                mark_prod_codi__in=codigos,
                mark_marketplace="mercado_livre",
            )
        )

        mapa_integracoes = {item.mark_prod_codi: item for item in integracoes}

        integracao_ids = [item.id for item in integracoes]

        anuncios = (
            MarketplaceAnuncio.objects.using(self.db_alias)
            .filter(maan_produto_id__in=integracao_ids)
            .order_by("id")
        )

        # mapear todos os anúncios/rascunhos por marketplace_produto_id
        mapa_anuncios = {}
        for anuncio in anuncios:
            mapa_anuncios.setdefault(anuncio.maan_produto_id, []).append(anuncio)

        for produto in produtos:
            integracao = mapa_integracoes.get(produto.prod_codi)

            produto.marketplace_integracao = integracao
            produto.marketplace_anuncio = None
            produto.marketplace_anuncios = []

            if integracao:
                lst = mapa_anuncios.get(integracao.id, [])
                produto.marketplace_anuncios = lst
                # compatibilidade: marketplace_anuncio continua sendo o último (mais recente)
                if lst:
                    produto.marketplace_anuncio = lst[-1]

            # ── preço e estoque base ─────────────────────────────────────────
            produto.preco_base   = self._buscar_preco(empresa, filial, produto.prod_codi)
            produto.estoque_base = self._buscar_estoque(empresa, filial, produto.prod_codi)

        return produtos

    # ─── preparar integração ─────────────────────────────────────────────────

    @transaction.atomic
    def preparar_produto(self, empresa, filial, prod_codi):
        produto = Produtos.objects.using(self.db_alias).get(
            prod_empr=str(empresa),
            prod_codi=prod_codi,
        )

        if not produto.prod_codi_merc_livr:
            raise ValueError("Produto ainda não possui SKU Mercado Livre.")

        obj, created = MarketplaceProduto.objects.using(self.db_alias).get_or_create(
            mark_empr=empresa,
            mark_fili=filial,
            mark_prod_codi=produto.prod_codi,
            mark_marketplace="mercado_livre",
            defaults={
                "mark_sku_codi": produto.prod_codi_merc_livr,
                "mark_stat": "PENDENTE",
                "mark_sync_preco": True,
                "mark_sync_esto": True,
            },
        )

        if not created:
            obj.mark_sku_codi = produto.prod_codi_merc_livr
            obj.mark_stat = "PENDENTE"
            obj.save(
                using=self.db_alias,
                update_fields=["mark_sku_codi", "mark_stat", "mark_atua_em"],
            )

        return obj, created