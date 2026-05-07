from datetime import date
from django.db.models import Exists, F, IntegerField, OuterRef, Q, Subquery, DateField
from django.db.models.functions import Cast, Coalesce

from Entidades.models import Entidades
from Pisos.models import Orcamentopisos, Pedidospisos


class ClienteSemMovimentoService:
    def __init__(self, banco: str):
        self.banco = banco

    def _cliente_ref(self):
        return Cast(OuterRef("enti_clie"), IntegerField())

    def _clean_int(self, value):
        if value in [None, "", "None", "null", "undefined"]:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _clean_text(self, value):
        if value in [None, "", "None", "null", "undefined"]:
            return None

        value = str(value).strip()
        return value or None

    def listar(
        self,
        *,
        empresa=None,
        filial=None,
        data_inicial: date | None = None,
        data_final: date | None = None,
        cliente_nome: str | None = None,
        vendedor_nome: str | None = None,
    ):
        empresa = self._clean_int(empresa)
        filial = self._clean_int(filial)
        cliente_nome = self._clean_text(cliente_nome)
        vendedor_nome = self._clean_text(vendedor_nome)

        clientes = Entidades.objects.using(self.banco).all()

        if empresa:
            clientes = clientes.filter(enti_empr=empresa)

        if cliente_nome:
            clientes = clientes.filter(enti_nome__icontains=cliente_nome)

        vendedores_ids = None

        if vendedor_nome:
            if vendedor_nome.isdigit():
                vendedores_ids = [int(vendedor_nome)]
            else:
                vendedores_qs = Entidades.objects.using(self.banco).filter(
                    enti_nome__icontains=vendedor_nome,
                    enti_tipo_enti="VE",
                )

                if empresa:
                    vendedores_qs = vendedores_qs.filter(enti_empr=empresa)

                vendedores_ids = list(
                    vendedores_qs.values_list("enti_clie", flat=True)[:200]
                )

            if not vendedores_ids:
                return clientes.none()

            clientes = clientes.filter(enti_vend__in=vendedores_ids)

        _pedido_data = Coalesce(
            Cast(F("pedi_data"), DateField()),
            Cast(F("field_log_data"), DateField()),
        )
        _orcamento_data = Coalesce(
            Cast(F("orca_data"), DateField()),
            Cast(F("field_log_data"), DateField()),
        )

        pedidos_base = (
            Pedidospisos.objects.using(self.banco)
            .filter(pedi_clie=self._cliente_ref())
            .annotate(_d=_pedido_data)
        )
        orcamentos_base = (
            Orcamentopisos.objects.using(self.banco)
            .filter(orca_clie=self._cliente_ref())
            .annotate(_d=_orcamento_data)
        )

        if empresa:
            pedidos_base = pedidos_base.filter(pedi_empr=empresa)
            orcamentos_base = orcamentos_base.filter(orca_empr=empresa)

        if filial:
            pedidos_base = pedidos_base.filter(pedi_fili=filial)
            orcamentos_base = orcamentos_base.filter(orca_fili=filial)

        if vendedores_ids:
            pedidos_base = pedidos_base.filter(pedi_vend__in=vendedores_ids)
            orcamentos_base = orcamentos_base.filter(orca_vend__in=vendedores_ids)

        pedidos_periodo = pedidos_base
        orcamentos_periodo = orcamentos_base

        if data_inicial:
            pedidos_periodo = pedidos_periodo.filter(_d__gte=data_inicial)
            orcamentos_periodo = orcamentos_periodo.filter(_d__gte=data_inicial)

        if data_final:
            pedidos_periodo = pedidos_periodo.filter(_d__lte=data_final)
            orcamentos_periodo = orcamentos_periodo.filter(_d__lte=data_final)

        clientes = clientes.annotate(
            tem_pedido_total=Exists(pedidos_base),
            tem_orcamento_total=Exists(orcamentos_base),
            tem_pedido_periodo=Exists(pedidos_periodo),
            tem_orcamento_periodo=Exists(orcamentos_periodo),

            ultimo_pedido=Subquery(
                pedidos_base
                .order_by("-_d")
                .values("_d")[:1],
                output_field=DateField(),
            ),

            ultimo_orcamento=Subquery(
                orcamentos_base
                .order_by("-_d")
                .values("_d")[:1],
                output_field=DateField(),
            ),
        ).filter(
            Q(tem_pedido_total=True) | Q(tem_orcamento_total=True),
            tem_pedido_periodo=False,
            tem_orcamento_periodo=False,
        )

        return clientes.order_by("enti_nome")
