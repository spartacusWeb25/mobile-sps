from datetime import date, datetime

from django.db.models import Sum
from django.views.generic import ListView

from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin

from Pisos.models import Orcamentopisos, StatusPisos
from Pisos.services.status_pisos_service import StatusPisosService

from Entidades.models import Entidades


class OrcamentoPisosListView(VendedorEntidadeMixin, ListView):
    model = Orcamentopisos
    template_name = "Pisos/orcamentos_listar.html"
    context_object_name = "orcamentos"
    paginate_by = 50

    def get_queryset(self):
        self.banco = get_db_from_slug(self.kwargs["slug"])
        data_min = date(2020, 1, 1)

        qs = (
            Orcamentopisos.objects
            .using(self.banco)
            .filter(orca_data__gte=data_min)
            .only(
                "orca_empr",
                "orca_fili",
                "orca_nume",
                "orca_clie",
                "orca_vend",
                "orca_data",
                "orca_tota",
                "orca_stat",
            )
            .order_by("-orca_nume")
        )

        qs = self.filter_por_vendedor(qs, "orca_vend")

        numero = self.request.GET.get("orca_nume")
        cliente_nome = self.request.GET.get("cliente_nome")
        vendedor_nome = self.request.GET.get("vendedor_nome")
        status = self.request.GET.get("orca_stat")
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        if numero:
            qs = qs.filter(orca_nume=numero)

        if status not in (None, ""):
            qs = qs.filter(orca_stat=status)

        if data_inicio:
            try:
                di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                qs = qs.filter(orca_data__gte=di)
            except ValueError:
                pass

        if data_fim:
            try:
                df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                qs = qs.filter(orca_data__lte=df)
            except ValueError:
                pass

        if cliente_nome:
            clientes_ids = Entidades.objects.using(self.banco).filter(
                enti_nome__icontains=cliente_nome
            ).values_list("enti_clie", flat=True)

            qs = qs.filter(orca_clie__in=list(clientes_ids))

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

            qs = qs.filter(orca_vend__in=list(vendedores_ids))

        rows = list(qs)

        entidades_ids = set()
        for o in rows:
            if o.orca_clie:
                entidades_ids.add(o.orca_clie)
            if o.orca_vend:
                entidades_ids.add(o.orca_vend)

        entidades = Entidades.objects.using(self.banco).filter(
            enti_clie__in=entidades_ids
        )

        nomes = {
            e.enti_clie: e.enti_nome
            for e in entidades
        }

        if rows:
            empresa = rows[0].orca_empr
            filial = rows[0].orca_fili

            status_map = StatusPisosService.mapa_status(
                banco=self.banco,
                empresa=empresa,
                filial=filial,
                tipo=StatusPisos.TIPO_ORCAMENTO,
            )
        else:
            status_map = {}

        for o in rows:
            status_obj = status_map.get(o.orca_stat)

            o.cliente_nome = nomes.get(o.orca_clie, "")
            o.vendedor_nome = nomes.get(o.orca_vend, "")
            o.status_desc = status_obj.stat_desc if status_obj else "Sem status"
            o.status_cor = status_obj.stat_cor if status_obj else "#6c757d"

        return rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_min = date(2020, 1, 1)

        base_qs = Orcamentopisos.objects.using(self.banco).filter(
            orca_data__gte=data_min
        )
        base_qs = self.filter_por_vendedor(base_qs, "orca_vend")

        context["slug"] = self.kwargs["slug"]

        # Get list of vendedores for the dropdown
        from Entidades.models import Entidades
        vendedores = Entidades.objects.using(self.banco).filter(
            enti_tipo_enti='VE'
        ).values('enti_clie', 'enti_nome').order_by('enti_nome')
        context["vendedores_list"] = list(vendedores)

        context["metricas"] = {
            "total_orcamentos": base_qs.count(),
            "total_valor": base_qs.aggregate(total=Sum("orca_tota")).get("total") or 0,
            "total_exportados": base_qs.filter(orca_stat=2).count(),
            "total_cancelados": base_qs.filter(orca_stat=3).count(),
        }

        # Set default dates to current month if not provided
        today = date.today()
        first_day_of_month = date(today.year, today.month, 1)

        # Handle multiple vendedor_nome values (always return a list)
        vendedor_nome_filter = self.request.GET.getlist("vendedor_nome")

        context["filtros"] = {
            "orca_nume": self.request.GET.get("orca_nume", ""),
            "cliente_nome": self.request.GET.get("cliente_nome", ""),
            "vendedor_nome": vendedor_nome_filter,
            "orca_stat": self.request.GET.get("orca_stat", ""),
            "data_inicio": self.request.GET.get("data_inicio", first_day_of_month.strftime('%Y-%m-%d')),
            "data_fim": self.request.GET.get("data_fim", today.strftime('%Y-%m-%d')),
        }

        return context