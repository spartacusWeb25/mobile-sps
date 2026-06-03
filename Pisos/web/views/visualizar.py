from django.shortcuts import get_object_or_404, render
from django.db.models import Value
from django.db.models.functions import Coalesce, Lower
import Entidades
from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from Pisos.models import Pedidospisos, Itenspedidospisos
from Produtos.models import Produtos
from Entidades.models import Entidades


def visualizar_pedido_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    # Sanitize pk - ensure it's a valid integer
    try:
        pk = int(pk)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404("Pedido inválido")

    mix = VendedorEntidadeMixin()
    mix.request = request

    qs = mix.filter_por_vendedor(
        Pedidospisos.objects.using(banco),
        'pedi_vend'
    )

    # First try without empresa/filial filters
    try:
        pedido = get_object_or_404(qs, pedi_nume=pk)
    except ValueError as e:
        # Handle database data corruption (invalid dates)
        if "year" in str(e).lower() or "out of range" in str(e).lower():
            # Fix corrupted dates in database
            from datetime import date
            from django.db import connections
            current_date = date.today()

            with connections[banco].cursor() as cursor:
                cursor.execute(
                    "UPDATE Pedidospisos SET pedi_data = %s WHERE pedi_nume = %s",
                    [current_date, pk]
                )

            # Retry the query after fixing
            pedido = get_object_or_404(qs, pedi_nume=pk)
        raise
    except Exception:
        # If multiple results, try with empresa/filial filters from session
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

        if empresa_id:
            qs = qs.filter(pedi_empr=empresa_id)
        if filial_id:
            qs = qs.filter(pedi_fili=filial_id)

        try:
            pedido = get_object_or_404(qs, pedi_nume=pk)
        except ValueError as e:
            # Handle database data corruption (invalid dates)
            if "year" in str(e).lower() or "out of range" in str(e).lower():
                # Fix corrupted dates in database
                from datetime import date
                from django.db import connections
                current_date = date.today()

                with connections[banco].cursor() as cursor:
                    cursor.execute(
                        "UPDATE Pedidospisos SET pedi_data = %s WHERE pedi_nume = %s",
                        [current_date, pk]
                    )

                # Retry the query after fixing
                pedido = get_object_or_404(qs, pedi_nume=pk)
            raise

    itens = list(
        Itenspedidospisos.objects.using(banco)
        .filter(
            item_empr=pedido.pedi_empr,
            item_fili=pedido.pedi_fili,
            item_pedi=pk,
        )
        .annotate(_amb_sort=Lower(Coalesce("item_nome_ambi", Value(""))))
        .order_by("_amb_sort", "item_ambi", "item_nume")
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
