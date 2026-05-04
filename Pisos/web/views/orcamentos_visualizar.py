from django.shortcuts import get_object_or_404, render

from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from Pisos.models import Itensorcapisos, Orcamentopisos


def visualizar_orcamento_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)
    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Orcamentopisos.objects.using(banco), 'orca_vend')
    orcamento = get_object_or_404(qs, orca_nume=pk)
    itens = Itensorcapisos.objects.using(banco).filter(
        item_empr=orcamento.orca_empr,
        item_fili=orcamento.orca_fili,
        item_orca=orcamento.orca_nume,
    ).order_by("item_nume", "item_ambi")
    return render(request, "Pisos/orcamento_visualizar.html", {"slug": slug, "orcamento": orcamento, "itens": itens})

