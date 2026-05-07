from Entidades.models import Entidades
from core.utils import get_licenca_db_config
from core.mixins.vendedor_mixin import VendedorEntidadeMixin


class VendedorResponsavelEntidadeMixin(VendedorEntidadeMixin):
    def get_vendedor_responsavel_ids(self, *, banco=None, param_name="vendedor"):
        banco = banco or get_licenca_db_config(self.request)
        if not banco:
            return []

        if self._usuario_eh_perfil_vendedores(banco=banco):
            entidade_vendedor = self.get_entidade_vendedor(banco=banco)
            vend_id = getattr(entidade_vendedor, "enti_clie", None)
            try:
                return [int(vend_id)] if vend_id not in [None, ""] else []
            except Exception:
                return []

        raw = (self.request.GET.get(param_name) or self.request.GET.get("enti_vend") or "").strip()
        if not raw:
            return []

        if raw.isdigit():
            try:
                return [int(raw)]
            except Exception:
                return []

        empresa = (
            self.request.session.get("empresa_id")
            or self.request.headers.get("X-Empresa")
        )
        try:
            empresa = int(empresa) if empresa not in [None, ""] else None
        except Exception:
            empresa = None

        qs = Entidades.objects.using(banco).filter(
            enti_tipo_enti__in=["VE", "AM", "FU"],
            enti_situ="1",
            enti_nome__icontains=raw,
        )
        if empresa is not None:
            qs = qs.filter(enti_empr=empresa)

        return list(qs.values_list("enti_clie", flat=True)[:200])

    def filter_entidades_por_vendedor_responsavel(self, queryset, *, banco=None, campo="enti_vend", param_name="vendedor"):
        raw = (self.request.GET.get(param_name) or self.request.GET.get("enti_vend") or "").strip()
        ids = self.get_vendedor_responsavel_ids(banco=banco, param_name=param_name)
        if ids:
            return queryset.filter(**{f"{campo}__in": ids})
        if raw:
            return queryset.none()
        return queryset
