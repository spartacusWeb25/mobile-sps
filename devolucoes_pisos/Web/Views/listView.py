from django.views.generic import ListView

from core.utils import get_db_from_slug
from Entidades.models import Entidades
from Pisos.models import Pedidospisos
from devolucoes_pisos.models import Creditotrocas
from devolucoes_pisos.services.troca_devolucao_service import DevolucaoPedidoPisoService


class DevolucoesPisosListView(ListView):
    template_name = "DevolucoesPisos/devolucoes_listar.html"
    context_object_name = "devolucoes"

    def get_queryset(self):
        self.slug = self.kwargs.get("slug")
        self.banco = get_db_from_slug(self.slug)
        self.empresa = int(self.request.session.get("empresa") or self.request.session.get("empr") or 1)
        self.filial = int(self.request.session.get("filial") or self.request.session.get("fili") or 1)

        filtros = {
            "devo_empr": self.empresa,
            "devo_fili": self.filial,
            "devo_pedi": self.request.GET.get("devo_pedi"),
        }
        return list(DevolucaoPedidoPisoService.listar(self.banco, filtros=filtros))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        devolucoes = list(context.get("devolucoes") or [])

        pedidos_numeros = [d.devo_pedi for d in devolucoes if getattr(d, "devo_pedi", None)]
        pedidos = (
            Pedidospisos.objects.using(self.banco)
            .filter(pedi_nume__in=pedidos_numeros)
            .only("pedi_nume", "pedi_clie", "pedi_vend", "pedi_data", "pedi_tota")
        )
        pedido_map = {p.pedi_nume: p for p in pedidos}

        clientes_ids = set()
        for d in devolucoes:
            p = pedido_map.get(getattr(d, "devo_pedi", None))
            if p and p.pedi_clie:
                clientes_ids.add(p.pedi_clie)

        nomes_clientes = {}
        if clientes_ids:
            entidades = Entidades.objects.using(self.banco).filter(
                enti_empr=self.empresa, enti_clie__in=list(clientes_ids)
            )
            nomes_clientes = {e.enti_clie: e.enti_nome for e in entidades}

        creditos_ids = [d.devo_cred for d in devolucoes if getattr(d, "devo_cred", None)]
        creditos_map = {}
        if creditos_ids:
            creditos = Creditotrocas.objects.using(self.banco).filter(cred_id__in=creditos_ids)
            creditos_map = {c.cred_id: c for c in creditos}

        for d in devolucoes:
            p = pedido_map.get(getattr(d, "devo_pedi", None))
            d.pedido = p
            if p:
                d.cliente_nome = nomes_clientes.get(p.pedi_clie, "")
            credito = creditos_map.get(getattr(d, "devo_cred", None))
            d.credito_valor = getattr(credito, "cred_fina_valo", None) if credito else None

        context["slug"] = self.slug
        context["empresa"] = self.empresa
        context["filial"] = self.filial
        context["devolucoes"] = devolucoes
        context["filtros"] = {
            "devo_pedi": self.request.GET.get("devo_pedi", ""),
        }
        return context

