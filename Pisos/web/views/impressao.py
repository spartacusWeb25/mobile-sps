from django.shortcuts import get_object_or_404, render
from django.http import Http404
 
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from core.utils import get_db_from_slug
from Pisos.models import Orcamentopisos, Pedidospisos
from Pisos.services.orcamento_impressao_service import OrcamentoPisosImpressaoService
from Pisos.services.pedido_impressao_service import PedidoPisosImpressaoService
 
 
def _get_empresa_filial_sessao(request):
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
    try:
        empresa_id = int(empresa_id) if empresa_id not in (None, "") else None
    except Exception:
        empresa_id = None
    try:
        filial_id = int(filial_id) if filial_id not in (None, "") else None
    except Exception:
        filial_id = None
    return empresa_id, filial_id


def imprimir_pedido_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    # Sanitize pk - ensure it's a valid integer
    try:
        pk = int(pk)
    except (ValueError, TypeError):
        raise Http404("Pedido inválido")

    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Pedidospisos.objects.using(banco), "pedi_vend")
    empresa_id, filial_id = _get_empresa_filial_sessao(request)

    def _buscar_pedido():
        pedido_qs = qs.filter(pedi_nume=pk)
        if empresa_id:
            pedido_qs = pedido_qs.filter(pedi_empr=empresa_id)
        if filial_id:
            pedido_qs = pedido_qs.filter(pedi_fili=filial_id)

        try:
            return pedido_qs.get()
        except Pedidospisos.DoesNotExist:
            if empresa_id or filial_id:
                raise Http404("Pedido não encontrado para a empresa/filial selecionada.")
            raise Http404("Pedido não encontrado.")
        except Pedidospisos.MultipleObjectsReturned:
            if empresa_id or filial_id:
                raise Http404("Pedido duplicado para a empresa/filial selecionada.")
            raise Http404("Pedido duplicado. Selecione empresa e filial para visualizar/imprimir.")

    try:
        pedido = _buscar_pedido()
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
            pedido = _buscar_pedido()
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
        raise Http404("Orçamento inválido")

    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Orcamentopisos.objects.using(banco), "orca_vend")
    empresa_id, filial_id = _get_empresa_filial_sessao(request)

    def _buscar_orcamento():
        orc_qs = qs.filter(orca_nume=pk)
        if empresa_id:
            orc_qs = orc_qs.filter(orca_empr=empresa_id)
        if filial_id:
            orc_qs = orc_qs.filter(orca_fili=filial_id)

        try:
            return orc_qs.get()
        except Orcamentopisos.DoesNotExist:
            if empresa_id or filial_id:
                raise Http404("Orçamento não encontrado para a empresa/filial selecionada.")
            raise Http404("Orçamento não encontrado.")
        except Orcamentopisos.MultipleObjectsReturned:
            if empresa_id or filial_id:
                raise Http404("Orçamento duplicado para a empresa/filial selecionada.")
            raise Http404("Orçamento duplicado. Selecione empresa e filial para visualizar/imprimir.")

    try:
        orcamento = _buscar_orcamento()
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
            orcamento = _buscar_orcamento()
        raise
 
    contexto = OrcamentoPisosImpressaoService.obter_contexto(banco=banco, orcamento=orcamento)
    contexto.update({"slug": slug, "orcamento": orcamento})
 
    return render(request, "Pisos/orcamento_impressao.html", contexto)
