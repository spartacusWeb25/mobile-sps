from django.views.generic import ListView
from core.utils import get_db_from_slug
from Entidades.models import Entidades
from ...service.clientes_sem_movimento import ClienteSemMovimentoService
from core.mixins.vendedor_responsavel_entidade_mixin import VendedorResponsavelEntidadeMixin
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone


class ClientesSemMovimentoListView(VendedorResponsavelEntidadeMixin, ListView):
    model = Entidades
    template_name = "ControleDeVisitas/clientes_sem_movimento.html"
    context_object_name = "clientes"
    paginate_by = 50  

    @staticmethod
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%d%m%Y", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    def get_queryset(self):
        self.banco = get_db_from_slug(self.kwargs["slug"])
        vendedor_param = (self.request.GET.get("vendedor") or "").strip()
        vendedor_nome = vendedor_param or None
        vendedor_ids = self.get_vendedor_responsavel_ids(banco=self.banco, param_name="vendedor")
        if vendedor_ids and len(vendedor_ids) == 1:
            vendedor_nome = str(vendedor_ids[0])
        service = ClienteSemMovimentoService(self.banco)

        self.data_inicial_obj = self._parse_date(self.request.GET.get("data_inicial"))
        self.data_final_obj = self._parse_date(self.request.GET.get("data_final"))
        if self.data_inicial_obj is None and self.data_final_obj is None:
            self.data_final_obj = timezone.localdate() if getattr(settings, "USE_TZ", False) else datetime.now().date()
            self.data_inicial_obj = self.data_final_obj - timedelta(days=90)
        empresa = (self.request.GET.get("empresa") or "").strip() or self.request.session.get("empresa_id")
        filial = (self.request.GET.get("filial") or "").strip() or self.request.session.get("filial_id")
        qs = service.listar(
            empresa=empresa,
            filial=filial,
            data_inicial=self.data_inicial_obj,
            data_final=self.data_final_obj,
            cliente_nome=self.request.GET.get("cliente"),
            vendedor_nome=vendedor_nome,
        )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        def _to_input_date_obj(value):
            return value.strftime("%Y-%m-%d") if value else ""

        context["slug"] = self.kwargs["slug"]
        context["filtros"] = self.request.GET
        context["empresa"] = self.request.session.get("empresa_id")
        context["filial"] = self.request.session.get("filial_id")
        context["data_inicial"] = _to_input_date_obj(getattr(self, "data_inicial_obj", None))
        context["data_final"] = _to_input_date_obj(getattr(self, "data_final_obj", None))
        context["data_inicial_obj"] = getattr(self, "data_inicial_obj", None)
        context["data_final_obj"] = getattr(self, "data_final_obj", None)

        filtros_sem_page = self.request.GET.copy()
        try:
            filtros_sem_page.pop("page", None)
        except Exception:
            pass
        context["qs_sem_page"] = filtros_sem_page.urlencode()

        return context
