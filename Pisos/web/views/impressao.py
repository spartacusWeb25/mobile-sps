
from django.shortcuts import get_object_or_404, render
 
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from core.utils import get_db_from_slug
from Pisos.models import Orcamentopisos, Pedidospisos
from Pisos.services.orcamento_impressao_service import OrcamentoPisosImpressaoService
from Pisos.services.pedido_impressao_service import PedidoPisosImpressaoService
 
 
def imprimir_pedido_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)
 
    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Pedidospisos.objects.using(banco), "pedi_vend")
    pedido = get_object_or_404(qs, pedi_nume=pk)
 
    contexto = PedidoPisosImpressaoService.obter_contexto(banco=banco, pedido=pedido)
    contexto.update({"slug": slug, "pedido": pedido})
 
    return render(request, "Pisos/pedido_impressao.html", contexto)
 
 
def imprimir_orcamento_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)
 
    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Orcamentopisos.objects.using(banco), "orca_vend")
    orcamento = get_object_or_404(qs, orca_nume=pk)
 
    contexto = OrcamentoPisosImpressaoService.obter_contexto(banco=banco, orcamento=orcamento)
    contexto.update({"slug": slug, "orcamento": orcamento})
 
    return render(request, "Pisos/orcamento_impressao.html", contexto)