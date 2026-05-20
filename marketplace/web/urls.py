from django.urls import path

from marketplace.web.views import (
    MarketplaceProdutoListView,
    PrepararProdutoMarketplaceView,
    GerarRascunhoAnuncioView,
    PublicarAnuncioMercadoLivreView,
    PublicarTodosRascunhosView,
)

from marketplace.web.views_config import (
    MarketplaceConfigPainelView,
    MarketplaceMlSalvarContaView,
    MarketplaceMlRenovarTokenView,
)
from marketplace.web.gerar_rascunhos_lote import GerarRascunhosLoteView



app_name = "marketplace"

urlpatterns = [
    path(
        "configuracoes/",
        MarketplaceConfigPainelView.as_view(),
        name="configuracoes",
    ),
    path(
        "configuracoes/mercado-livre/salvar/",
        MarketplaceMlSalvarContaView.as_view(),
        name="ml_salvar_conta",
    ),
    path(
        "produtos-integraveis/",
        MarketplaceProdutoListView.as_view(),
        name="produtos_integraveis",
    ),
    path(
        "produtos/<str:prod_codi>/preparar/",
        PrepararProdutoMarketplaceView.as_view(),
        name="preparar_produto",
    ),
    path(
        "produtos/<int:marketplace_produto_id>/gerar-rascunho/",
        GerarRascunhoAnuncioView.as_view(),
        name="gerar_rascunho_anuncio",
    ),
    path(
        "produtos/<int:anuncio_id>/publicar/",
        PublicarAnuncioMercadoLivreView.as_view(),
        name="publicar_anuncio",
    ),
    path(
        "produtos/<int:marketplace_produto_id>/publicar-todos/",
        PublicarTodosRascunhosView.as_view(),
        name="publicar_todos_rascunhos",
    ),
    path(
    "configuracoes/mercado-livre/renovar-token/",
    MarketplaceMlRenovarTokenView.as_view(),
    name="ml_renovar_token",
),
    path(
        "produtos/<int:marketplace_produto_id>/gerar-rascunhos-lote/",
        GerarRascunhosLoteView.as_view(),
        name="gerar_rascunhos_lote",
    ),
]