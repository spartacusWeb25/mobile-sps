# produtos/web/views/produto_marketplace_views.py

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from core.utils import get_db_from_slug
from Produtos.models import Produtos
from Produtos.services.produto_marketplace_service import ProdutoMarketplaceService


class GerarCodigoMercadoLivreView(View):
    def post(self, request, slug, prod_codi):
        db_alias = get_db_from_slug(slug)

        produto = get_object_or_404(
            Produtos.objects.using(db_alias),
            prod_codi=prod_codi,
        )

        service = ProdutoMarketplaceService(db_alias=db_alias)
        codigo = service.gerar_codigo_mercado_livre(produto)

        messages.success(
            request,
            f"Código Mercado Livre gerado: {codigo}",
        )

        return redirect(request.META.get("HTTP_REFERER", "/"))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs['slug']
        return context
