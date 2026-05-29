
from django.shortcuts import get_object_or_404, render
 
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from core.utils import get_db_from_slug
from Pisos.models import Orcamentopisos, Pedidospisos
from Pisos.services.orcamento_impressao_service import OrcamentoPisosImpressaoService
from Pisos.services.pedido_impressao_service import PedidoPisosImpressaoService
 
 
def imprimir_pedido_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    # Sanitize pk - ensure it's a valid integer
    try:
        pk = int(pk)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404("Pedido inválido")

    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Pedidospisos.objects.using(banco), "pedi_vend")

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
 
    contexto = PedidoPisosImpressaoService.obter_contexto(banco=banco, pedido=pedido)
    contexto.update({"slug": slug, "pedido": pedido})
 
    return render(request, "Pisos/pedido_impressao.html", contexto)
 
 
def imprimir_orcamento_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    # Sanitize pk - ensure it's a valid integer
    try:
        pk = int(pk)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404("Orçamento inválido")

    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Orcamentopisos.objects.using(banco), "orca_vend")

    # First try without empresa/filial filters
    try:
        orcamento = get_object_or_404(qs, orca_nume=pk)
    except ValueError as e:
        # Handle database data corruption (invalid dates)
        if "year" in str(e).lower() or "out of range" in str(e).lower():
            # Fix corrupted dates in database
            from datetime import date
            from django.db import connections
            current_date = date.today()

            with connections[banco].cursor() as cursor:
                cursor.execute(
                    "UPDATE Orcamentopisos SET orca_data = %s, orca_data_prev_entr = %s WHERE orca_nume = %s",
                    [current_date, current_date, pk]
                )

            # Retry the query after fixing
            orcamento = get_object_or_404(qs, orca_nume=pk)
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
            qs = qs.filter(orca_empr=empresa_id)
        if filial_id:
            qs = qs.filter(orca_fili=filial_id)

        try:
            orcamento = get_object_or_404(qs, orca_nume=pk)
        except ValueError as e:
            # Handle database data corruption (invalid dates)
            if "year" in str(e).lower() or "out of range" in str(e).lower():
                # Fix corrupted dates in database
                from datetime import date
                from django.db import connections
                current_date = date.today()

                with connections[banco].cursor() as cursor:
                    cursor.execute(
                        "UPDATE Orcamentopisos SET orca_data = %s, orca_data_prev_entr = %s WHERE orca_nume = %s",
                        [current_date, current_date, pk]
                    )

                # Retry the query after fixing
                orcamento = get_object_or_404(qs, orca_nume=pk)
            raise
 
    contexto = OrcamentoPisosImpressaoService.obter_contexto(banco=banco, orcamento=orcamento)
    contexto.update({"slug": slug, "orcamento": orcamento})
 
    return render(request, "Pisos/orcamento_impressao.html", contexto)