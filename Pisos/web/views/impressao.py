
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

    # Get empresa and filial from session to uniquely identify the pedido
    empresa_id = (
        request.session.get('empresa_id')
        or request.session.get('empresa')
        or request.session.get('empr_codi')
    )
    filial_id = (
        request.session.get('filial_id')
        or request.session.get('filial')
        or request.session.get('fili_codi')
    )

    # Add empresa and filial filters to ensure unique result
    if empresa_id:
        qs = qs.filter(pedi_empr=empresa_id)
    if filial_id:
        qs = qs.filter(pedi_fili=filial_id)

    pedido = get_object_or_404(qs, pedi_nume=pk)
 
    contexto = PedidoPisosImpressaoService.obter_contexto(banco=banco, pedido=pedido)
    contexto.update({"slug": slug, "pedido": pedido})
 
    return render(request, "Pisos/pedido_impressao.html", contexto)
 
 
def imprimir_orcamento_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Orcamentopisos.objects.using(banco), "orca_vend")

    # Get empresa and filial from session to uniquely identify the orcamento
    empresa_id = (
        request.session.get('empresa_id')
        or request.session.get('empresa')
        or request.session.get('empr_codi')
    )
    filial_id = (
        request.session.get('filial_id')
        or request.session.get('filial')
        or request.session.get('fili_codi')
    )

    # Add empresa and filial filters to ensure unique result
    if empresa_id:
        qs = qs.filter(orca_empr=empresa_id)
    if filial_id:
        qs = qs.filter(orca_fili=filial_id)

    orcamento = get_object_or_404(qs, orca_nume=pk)
 
    contexto = OrcamentoPisosImpressaoService.obter_contexto(banco=banco, orcamento=orcamento)
    contexto.update({"slug": slug, "orcamento": orcamento})
 
    return render(request, "Pisos/orcamento_impressao.html", contexto)