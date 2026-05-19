from core.utils import get_db_from_slug
from ...services.plano_service import PlanoGerencialService


class PlanoGerencialContextMixin:
    def get_slug(self):
        return self.kwargs.get("slug")

    def get_db_alias(self):
        slug = self.get_slug()
        return get_db_from_slug(slug) if slug else "default"

    def get_empresa(self):
        return int(self.request.session.get("empresa_id", 1))

    def get_service(self):
        return PlanoGerencialService(
            empresa=self.get_empresa(),
            db_alias=self.get_db_alias(),
        )
