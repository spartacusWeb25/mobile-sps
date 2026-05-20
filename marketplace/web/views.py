from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from core.utils import get_db_from_slug

from marketplace.services.marketplace_anuncio_service import MarketplaceAnuncioService
from ..services.produto_integracao_service import MarketplaceProdutoService


class MarketplaceProdutoListView(TemplateView):
    template_name = "marketplace/produtos_integraveis_list.html"

    def get_db_context(self):
        slug = self.kwargs.get("slug")
        return {
            "slug": slug,
            "db_alias": get_db_from_slug(slug),
            "empresa": self.request.session.get("empresa_id", 1),
            "filial": self.request.session.get("filial_id", 1),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ctx = self.get_db_context()

        service = MarketplaceProdutoService(db_alias=ctx["db_alias"])

        context["slug"] = ctx["slug"]
        context["empresa"] = ctx["empresa"]
        context["filial"] = ctx["filial"]
        context["produtos"] = service.listar_produtos_com_sku_ml(
            empresa=ctx["empresa"],
            filial=ctx["filial"],
        )

        return context


class PrepararProdutoMarketplaceView(View):
    def post(self, request, slug, prod_codi):
        db_alias = get_db_from_slug(slug)

        empresa = request.session.get("empresa_id", 1)
        filial = request.session.get("filial_id", 1)

        service = MarketplaceProdutoService(db_alias=db_alias)

        try:
            _, created = service.preparar_produto(
                empresa=empresa,
                filial=filial,
                prod_codi=prod_codi,
            )

            if created:
                messages.success(request, "Produto preparado para integração.")
            else:
                messages.info(request, "Produto já estava preparado e foi atualizado.")

        except Exception as e:
            messages.error(request, str(e))

        return redirect(request.META.get("HTTP_REFERER", "/"))




class GerarRascunhoAnuncioView(View):
    def post(self, request, slug, marketplace_produto_id):
        db_alias = get_db_from_slug(slug)

        empresa = request.session.get("empresa_id", 1)
        filial = request.session.get("filial_id", 1)

        service = MarketplaceAnuncioService(db_alias=db_alias)

        try:
            _, created = service.gerar_rascunho(
                empresa=empresa,
                filial=filial,
                marketplace_produto_id=marketplace_produto_id,
            )

            if created:
                messages.success(request, "Rascunho do anúncio gerado com sucesso.")
            else:
                messages.info(request, "Rascunho do anúncio atualizado.")

        except Exception as e:
            messages.error(request, str(e))

        return redirect(request.META.get("HTTP_REFERER", "/"))



class PublicarAnuncioMercadoLivreView(View):
    def post(self, request, slug, anuncio_id):
        db_alias = get_db_from_slug(slug)

        empresa = request.session.get("empresa_id", 1)
        filial = request.session.get("filial_id", 1)
        slug = slug
        

        service = MarketplaceAnuncioService(db_alias=db_alias)

        try:
            anuncio = service.publicar_rascunho(
                empresa=empresa,
                filial=filial,
                anuncio_id=anuncio_id,
            )

            messages.success(
                request,
                f"Anúncio publicado no Mercado Livre: {anuncio.maan_item_id}",
            )

        except Exception as e:
            messages.error(request, str(e))

        return redirect(request.META.get("HTTP_REFERER", "/"))


class PublicarTodosRascunhosView(View):
    def post(self, request, slug, marketplace_produto_id):
        db_alias = get_db_from_slug(slug)

        empresa = request.session.get("empresa_id", 1)
        filial = request.session.get("filial_id", 1)

        service = MarketplaceAnuncioService(db_alias=db_alias)

        try:
            resultados = service.publicar_rascunhos(
                empresa=empresa,
                filial=filial,
                marketplace_produto_id=marketplace_produto_id,
            )

            success = len(resultados.get("success", []))
            failed = resultados.get("failed", [])
            skipped = len(resultados.get("skipped", []))

            msg = f"{success} publicado(s). {skipped} ignorado(s)."
            if failed:
                msg += f" {len(failed)} falharam."
                # anexar até 3 erros para debug rápido
                for f in failed[:3]:
                    msg += f" Erro {f.get('id')}: {f.get('error')};"

            messages.success(request, msg)

        except Exception as e:
            messages.error(request, str(e))

        return redirect(request.META.get("HTTP_REFERER", "/"))