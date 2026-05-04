from django.shortcuts import get_object_or_404, render
from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from Pisos.models import Pedidospisos, Itenspedidospisos


def visualizar_pedido_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)
    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Pedidospisos.objects.using(banco), 'pedi_vend')
    pedido = get_object_or_404(qs, pedi_nume=pk)
    itens = Itenspedidospisos.objects.using(banco).filter(item_pedi=pk)
    return render(request, "Pisos/visualizar.html", {"slug": slug, "pedido": pedido, "itens": itens})
