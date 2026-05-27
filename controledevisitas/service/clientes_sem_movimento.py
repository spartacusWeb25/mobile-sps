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
        vendedores_ids: list[int] | None = None,
        somente_carteira: bool = False,
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

        vendedores_ids_int = []
        vendedores_ids_str = []

        if vendedores_ids is None and vendedor_nome:
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

        if vendedores_ids is not None:
            for v in vendedores_ids:
                if v is None or v == "":
                    continue
                try:
                    vendedores_ids_int.append(int(v))
                except (TypeError, ValueError):
                    pass
                try:
                    vendedores_ids_str.append(str(v))
                except Exception:
                    pass

            vendedores_ids_int = [v for v in vendedores_ids_int if v is not None]
            vendedores_ids_str = [v for v in vendedores_ids_str if v not in [None, ""]]

            if not vendedores_ids_int and not vendedores_ids_str:
                return clientes.none()

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

        if vendedores_ids_int or vendedores_ids_str:
            filtro_ped = Q()
            if vendedores_ids_int:
                filtro_ped |= Q(pedi_vend__in=vendedores_ids_int)
            if vendedores_ids_str:
                filtro_ped |= Q(pedi_vend__in=vendedores_ids_str)

            filtro_orc = Q()
            if vendedores_ids_int:
                filtro_orc |= Q(orca_vend__in=vendedores_ids_int)
            if vendedores_ids_str:
                filtro_orc |= Q(orca_vend__in=vendedores_ids_str)

            pedidos_vendedor_base = pedidos_base.filter(filtro_ped)
            orcamentos_vendedor_base = orcamentos_base.filter(filtro_orc)

            clientes = clientes.annotate(
                tem_pedido_vendedor=Exists(pedidos_vendedor_base),
                tem_orcamento_vendedor=Exists(orcamentos_vendedor_base),
            )

            if somente_carteira:
                clientes = clientes.filter(
                    Q(enti_vend__in=vendedores_ids_int)
                    | Q(enti_vend__in=vendedores_ids_str)
                    | Q(tem_pedido_vendedor=True)
                    | Q(tem_orcamento_vendedor=True)
                )
            else:
                clientes = clientes.filter(
                    Q(enti_vend__in=vendedores_ids_int)
                    | Q(enti_vend__in=vendedores_ids_str)
                    | Q(tem_pedido_vendedor=True)
                    | Q(tem_orcamento_vendedor=True)
                )

        pedidos_periodo = pedidos_base
        orcamentos_periodo = orcamentos_base

        if data_inicial:
            pedidos_periodo = pedidos_periodo.filter(_d__gte=data_inicial)
            orcamentos_periodo = orcamentos_periodo.filter(_d__gte=data_inicial)

        if data_final:
            pedidos_periodo = pedidos_periodo.filter(_d__lte=data_final)
            orcamentos_periodo = orcamentos_periodo.filter(_d__lte=data_final)

        pedidos_antes = pedidos_base
        orcamentos_antes = orcamentos_base

        if data_inicial:
            pedidos_antes = pedidos_antes.filter(_d__lt=data_inicial)
            orcamentos_antes = orcamentos_antes.filter(_d__lt=data_inicial)

        ultimo_pedido_antes = Subquery(
            pedidos_antes.order_by("-_d").values("_d")[:1],
            output_field=DateField(),
        )

        ultimo_orcamento_antes = Subquery(
            orcamentos_antes.order_by("-_d").values("_d")[:1],
            output_field=DateField(),
        )

        empty_sub = Subquery(pedidos_base.none().values("_d")[:1], output_field=DateField())
        ultimo_pedido_antes_vend = empty_sub
        ultimo_orcamento_antes_vend = empty_sub

        if (vendedores_ids_int or vendedores_ids_str):
            filtro_ped = Q()
            if vendedores_ids_int:
                filtro_ped |= Q(pedi_vend__in=vendedores_ids_int)
            if vendedores_ids_str:
                filtro_ped |= Q(pedi_vend__in=vendedores_ids_str)

            filtro_orc = Q()
            if vendedores_ids_int:
                filtro_orc |= Q(orca_vend__in=vendedores_ids_int)
            if vendedores_ids_str:
                filtro_orc |= Q(orca_vend__in=vendedores_ids_str)

            pedidos_antes_vendedor = pedidos_antes.filter(filtro_ped)
            orcamentos_antes_vendedor = orcamentos_antes.filter(filtro_orc)

            ultimo_pedido_antes_vend = Subquery(
                pedidos_antes_vendedor.order_by("-_d").values("_d")[:1],
                output_field=DateField(),
            )

            ultimo_orcamento_antes_vend = Subquery(
                orcamentos_antes_vendedor.order_by("-_d").values("_d")[:1],
                output_field=DateField(),
            )

        clientes = clientes.annotate(
            tem_pedido_total=Exists(pedidos_base),
            tem_orcamento_total=Exists(orcamentos_base),
            tem_pedido_periodo=Exists(pedidos_periodo),
            tem_orcamento_periodo=Exists(orcamentos_periodo),

            ultimo_pedido=Subquery(
                pedidos_base.order_by("-_d").values("_d")[:1],
                output_field=DateField(),
            ),

            ultimo_orcamento=Subquery(
                orcamentos_base.order_by("-_d").values("_d")[:1],
                output_field=DateField(),
            ),

            ultimo_pedido_antes=ultimo_pedido_antes,
            ultimo_orcamento_antes=ultimo_orcamento_antes,
            ultimo_pedido_antes_vend=ultimo_pedido_antes_vend,
            ultimo_orcamento_antes_vend=ultimo_orcamento_antes_vend,
        ).filter(
            Q(tem_pedido_total=True) | Q(tem_orcamento_total=True),
            tem_pedido_periodo=False,
            tem_orcamento_periodo=False,
        )

        return clientes.order_by("-ultimo_orcamento_antes", "-ultimo_pedido_antes")
