from django.shortcuts import get_object_or_404, render

from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from Pisos.models import Itensorcapisos, Orcamentopisos
from Produtos.models import Produtos
from Entidades.models import Entidades


def visualizar_orcamento_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    mix = VendedorEntidadeMixin()
    mix.request = request

    qs = mix.filter_por_vendedor(
        Orcamentopisos.objects.using(banco),
        'orca_vend'
    )

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

    itens = list(
        Itensorcapisos.objects.using(banco).filter(
            item_empr=orcamento.orca_empr,
            item_fili=orcamento.orca_fili,
            item_orca=pk,
        )
    )

    produtos = Produtos.objects.using(banco).filter(
        prod_codi__in=[i.item_prod for i in itens]
    )
    cliente_obj = Entidades.objects.using(banco).filter(
        enti_empr=orcamento.orca_empr,
        enti_clie=orcamento.orca_clie,
    ).first()
    cliente_nome = cliente_obj.enti_nome if cliente_obj else ''

    vendedor_obj = Entidades.objects.using(banco).filter(
        enti_empr=orcamento.orca_empr,
        enti_vend=orcamento.orca_vend,
    ).first()
    vendedor_nome = vendedor_obj.enti_nome if vendedor_obj else ''

    mapa_produtos = {
        p.prod_codi: p
        for p in produtos
    }

    for item in itens:
        produto = mapa_produtos.get(item.item_prod)

        item.produto_obj = produto
        item.item_prod_ncm = getattr(produto, 'prod_ncm', '')
        item.item_prod_nome = getattr(produto, 'prod_nome', '')
        item.item_caix = item.item_caix or 0

    return render(
        request,
        "Pisos/orcamento_visualizar.html",
        {
            "slug": slug,
            "orcamento": orcamento,
            "itens": itens,
            "cliente_nome": cliente_nome,
            "vendedor_nome": vendedor_nome,
            "orcamento": orcamento,
        }
    )