import json
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect
from django.views import View

from core.utils import get_db_from_slug
from marketplace.services.marketplace_anuncio_service import MarketplaceAnuncioService


class GerarRascunhosLoteView(View):
    def post(self, request, slug, marketplace_produto_id):
        db_alias = get_db_from_slug(slug)

        empresa = request.session.get("empresa_id", 1)
        filial = request.session.get("filial_id", 1)

        raw = request.POST.get("anuncios_json", "[]")

        try:
            anuncios_config = json.loads(raw)

            for item in anuncios_config:
                if item.get("preco"):
                    item["preco"] = Decimal(str(item["preco"]))

                if item.get("estoque"):
                    item["estoque"] = Decimal(str(item["estoque"]))

            service = MarketplaceAnuncioService(db_alias=db_alias)

            # log básico para debugging: quantos itens chegaram e conteúdo (parcial)
            try:
                logger = __import__('logging').getLogger(__name__)
                logger.debug(f"Gerar rascunhos lote: itens={len(anuncios_config)} preview={{}}".format(str(anuncios_config)[:1000]))
            except Exception:
                pass

            anuncios = service.gerar_rascunhos(
                empresa=empresa,
                filial=filial,
                marketplace_produto_id=marketplace_produto_id,
                anuncios_config=anuncios_config,
            )

            messages.success(
                request,
                f"{len(anuncios)} rascunho(s) criado(s) com sucesso.",
            )

        except Exception as e:
            messages.error(request, str(e))

        return redirect(request.META.get("HTTP_REFERER", "/"))