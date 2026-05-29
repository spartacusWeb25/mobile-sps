from django.shortcuts import get_object_or_404, render
import Entidades
from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from Pisos.models import Pedidospisos, Itenspedidospisos
from Produtos.models import Produtos
from Entidades.models import Entidades


def visualizar_pedido_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    mix = VendedorEntidadeMixin()
    mix.request = request

    qs = mix.filter_por_vendedor(
        Pedidospisos.objects.using(banco),
        'pedi_vend'
    )

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

    itens = list(
        Itenspedidospisos.objects.using(banco).filter(
            item_empr=pedido.pedi_empr,
            item_fili=pedido.pedi_fili,
            item_pedi=pk,
        )
    )

    produtos = Produtos.objects.using(banco).filter(
        prod_codi__in=[i.item_prod for i in itens]
    )
    cliente_nome = get_object_or_404(
        Entidades.objects.using(banco),
        enti_empr=pedido.pedi_empr,
        enti_clie=pedido.pedi_clie,
    ).enti_nome

    mapa_produtos = {
        p.prod_codi: p
        for p in produtos
    }

    for item in itens:
        produto = mapa_produtos.get(item.item_prod)

        item.produto_obj = produto
        item.item_prod_ncm = getattr(produto, 'prod_ncm', '')
        item.item_caix = item.item_caix or 0
        item.item_quan = item.item_quan or 0
        item.item_m2 = item.item_m2 or 0
        item.item_prod_nome = getattr(produto, 'prod_nome', '')

    return render(
        request,
        "Pisos/visualizar.html",
        {
            "slug": slug,
            "pedido": pedido,
            "itens": itens,
            "cliente_nome": cliente_nome,
        }
    )