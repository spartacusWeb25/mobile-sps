from datetime import date, datetime

from django.db.models import Sum
from django.views.generic import ListView

from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin

from Pisos.models import Pedidospisos, StatusPisos
from Pisos.services.status_pisos_service import StatusPisosService

from Entidades.models import Entidades


class PedidopisosListView(VendedorEntidadeMixin, ListView):
    template_name = "Pisos/listar.html"
    context_object_name = "pedidos"
    paginate_by = 50

    def get_queryset(self):
        self.banco = get_db_from_slug(self.kwargs["slug"])
        data_min = date(2020, 1, 1)

        qs = (
            Pedidospisos.objects
            .using(self.banco)
            .filter(pedi_data__gte=data_min)
            .only(
                "pedi_empr",
                "pedi_fili",
                "pedi_nume",
                "pedi_clie",
                "pedi_vend",
                "pedi_data",
                "pedi_tota",
                "pedi_stat",
            )
            .order_by("-pedi_nume")
        )

        qs = self.filter_por_vendedor(qs, "pedi_vend")

        numero = self.request.GET.get("pedi_nume")
        cliente_nome = self.request.GET.get("cliente_nome")
        vendedor_nome = self.request.GET.get("vendedor_nome")
        status = self.request.GET.get("pedi_stat")
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        if numero:
            qs = qs.filter(pedi_nume=numero)

        if status not in (None, ""):
            qs = qs.filter(pedi_stat=status)

        if data_inicio:
            try:
                di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                qs = qs.filter(pedi_data__gte=di)
            except ValueError:
                pass

        if data_fim:
            try:
                df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                qs = qs.filter(pedi_data__lte=df)
            except ValueError:
                pass

        if cliente_nome:
            clientes_ids = Entidades.objects.using(self.banco).filter(
                enti_nome__icontains=cliente_nome
            ).values_list("enti_clie", flat=True)

            qs = qs.filter(pedi_clie__in=list(clientes_ids))

        if vendedor_nome:
            # Handle multiple seller names (always use getlist to get all selected values)
            vendedor_nomes = self.request.GET.getlist("vendedor_nome")
            
            # Build Q objects for each seller name with icontains
            from django.db.models import Q
            q_objects = Q()
            for nome in vendedor_nomes:
                if nome:
                    q_objects |= Q(enti_nome__icontains=nome)
            
            vendedores_ids = Entidades.objects.using(self.banco).filter(q_objects).values_list("enti_clie", flat=True)

            qs = qs.filter(pedi_vend__in=list(vendedores_ids))

        rows = list(qs)
        print("VEND IDS:", [p.pedi_vend for p in rows[:5]])

        entidades_ids = set()
        for p in rows:
            if p.pedi_clie:
                entidades_ids.add(p.pedi_clie)
            if p.pedi_vend:
                entidades_ids.add(p.pedi_vend)

        entidades = Entidades.objects.using(self.banco).filter(
            enti_clie__in=entidades_ids
        )
        print("ENTIDADES:", [(e.enti_clie, e.enti_nome) for e in entidades[:5]])

        nomes = {
            e.enti_clie: e.enti_nome
            for e in entidades
        }
        print("NOMES DICT:", nomes)

        if rows:
            empresa = rows[0].pedi_empr
            filial = rows[0].pedi_fili

            status_map = StatusPisosService.mapa_status(
                banco=self.banco,
                empresa=empresa,
                filial=filial,
                tipo=StatusPisos.TIPO_PEDIDO,
            )
        else:
            status_map = {}

        for p in rows:
            status_obj = status_map.get(p.pedi_stat)

            p.cliente_nome = nomes.get(p.pedi_clie, "")
            p.vendedor_nome = nomes.get(p.pedi_vend, "")
            p.status_desc = status_obj.stat_desc if status_obj else "Sem status"
            p.status_cor = status_obj.stat_cor if status_obj else "#6c757d"

        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_min = date(2020, 1, 1)

        base_qs = Pedidospisos.objects.using(self.banco).filter(
            pedi_data__gte=data_min
        )
        base_qs = self.filter_por_vendedor(base_qs, "pedi_vend")

        context["slug"] = self.kwargs["slug"]

        # Get list of vendedores for the dropdown
        from Entidades.models import Entidades
        vendedores = Entidades.objects.using(self.banco).filter(
            enti_tipo_enti='VE'
        ).values('enti_clie', 'enti_nome').order_by('enti_nome')
        context["vendedores_list"] = list(vendedores)

        context["metricas"] = {
            "total_pedidos": base_qs.count(),
            "total_valor": base_qs.aggregate(total=Sum("pedi_tota")).get("total") or 0,
            "total_concluidos": base_qs.filter(pedi_stat=6).count(),
            "total_abertos": base_qs.filter(pedi_stat=0).count(),
        }

        # Set default dates to current month if not provided
        today = date.today()
        first_day_of_month = date(today.year, today.month, 1)

        # Handle multiple vendedor_nome values (always return a list)
        vendedor_nome_filter = self.request.GET.getlist("vendedor_nome")

        context["filtros"] = {
            "pedi_nume": self.request.GET.get("pedi_nume", ""),
            "cliente_nome": self.request.GET.get("cliente_nome", ""),
            "vendedor_nome": vendedor_nome_filter,
            "pedi_stat": self.request.GET.get("pedi_stat", ""),
            "data_inicio": self.request.GET.get("data_inicio", first_day_of_month.strftime('%Y-%m-%d')),
            "data_fim": self.request.GET.get("data_fim", today.strftime('%Y-%m-%d')),
        }

        return context