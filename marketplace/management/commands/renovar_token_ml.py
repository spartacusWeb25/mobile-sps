from django.core.management.base import BaseCommand

from core.utils import get_db_from_slug
from marketplace.services.mercado_livre_token_service import MercadoLivreTokenService


class Command(BaseCommand):
    help = "Renova access token do Mercado Livre"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--empresa", required=True, type=int)
        parser.add_argument("--filial", required=True, type=int)

    def handle(self, *args, **options):
        slug = options["slug"]
        empresa = options["empresa"]
        filial = options["filial"]

        db_alias = get_db_from_slug(slug)

        service = MercadoLivreTokenService(db_alias=db_alias)
        conta = service.renovar_token(empresa=empresa, filial=filial)

        self.stdout.write(
            self.style.SUCCESS(
                f"Token ML renovado com sucesso para empresa {empresa}/{filial}. Expira em {conta.ml_expires_in}s."
            )
        )