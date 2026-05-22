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
    cliente_nome = get_object_or_404(
        Entidades.objects.using(banco),
        enti_empr=orcamento.orca_empr,
        enti_clie=orcamento.orca_clie,
    ).enti_nome
    vendedor_nome = get_object_or_404(
        Entidades.objects.using(banco),
        enti_empr=orcamento.orca_empr,
        enti_vend=orcamento.orca_vend,
    ).enti_nome

    mapa_produtos = {
        p.prod_codi: p
        for p in produtos
    }

    for item in itens:
        produto = mapa_produtos.get(item.item_prod)

        item.produto_obj = produto
        item.item_prod_ncm = getattr(produto, 'prod_ncm', '')
        item.item_prod_nome = getattr(produto, 'prod_nome', '')

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