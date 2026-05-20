from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from core.utils import get_db_from_slug
from marketplace.models import MarketplaceContasMl
from ..services.marketplace_config_service import MarketplaceConfigService
from marketplace.services.mercado_livre_token_service import MercadoLivreTokenService


class MarketplaceConfigPainelView(TemplateView):
    template_name = "marketplace/configuracoes/painel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        slug = self.kwargs.get("slug")
        db_alias = get_db_from_slug(slug)

        empresa = self.request.session.get("empresa_id", 1)
        filial = self.request.session.get("filial_id", 1)

        service = MarketplaceConfigService(db_alias=db_alias)

        context["slug"] = slug
        context["empresa"] = empresa
        context["filial"] = filial
        context["marketplaces"] = service.painel_configuracoes(
            empresa=empresa,
            filial=filial,
        )

        return context


class MarketplaceMlSalvarContaView(View):
    def post(self, request, slug):
        db_alias = get_db_from_slug(slug)

        empresa = request.session.get("empresa_id", 1)
        filial = request.session.get("filial_id", 1)

        access_token = request.POST.get("ml_access_token")
        refresh_token = request.POST.get("ml_refresh_token")
        expires_in = request.POST.get("ml_expires_in") or 0

        if not access_token or not refresh_token:
            messages.error(request, "Informe access token e refresh token.")
            return redirect("marketplace:configuracoes", slug=slug)

        MarketplaceContasMl.objects.using(db_alias).update_or_create(
            ml_empr=empresa,
            ml_fili=filial,
            defaults={
                "ml_access_token": access_token,
                "ml_refresh_token": refresh_token,
                "ml_expires_in": int(expires_in),
            },
        )

        messages.success(request, "Conta Mercado Livre salva com sucesso.")
        return redirect("marketplace:configuracoes", slug=slug)






class MarketplaceMlRenovarTokenView(View):
    def post(self, request, slug):
        db_alias = get_db_from_slug(slug)

        empresa = request.session.get("empresa_id", 1)
        filial = request.session.get("filial_id", 1)

        service = MercadoLivreTokenService(db_alias=db_alias)

        try:
            conta = service.renovar_token(empresa=empresa, filial=filial)
            messages.success(
                request,
                f"Token Mercado Livre renovado. Expira em {conta.ml_expires_in}s.",
            )
        except Exception as e:
            messages.error(request, str(e))

        return redirect("marketplace:configuracoes", slug=slug)