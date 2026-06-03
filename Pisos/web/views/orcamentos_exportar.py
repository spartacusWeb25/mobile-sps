import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from Pisos.models import Orcamentopisos
from Pisos.services.orcamento_exportar_service import OrcamentoExportarPedidoService


logger = logging.getLogger(__name__)


def exportar_orcamento_pedido(request, slug, numero):
    banco = get_db_from_slug(slug)

    # Sanitize numero - ensure it's a valid integer
    try:
        numero = int(numero)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404("Orçamento inválido")

    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Orcamentopisos.objects.using(banco), 'orca_vend')

    empresa_id = (
        request.session.get("empresa_id")
        or request.session.get("empresa")
        or request.session.get("empr_codi")
    )
    filial_id = (
        request.session.get("filial_id")
        or request.session.get("filial")
        or request.session.get("fili_codi")
    )
    if not empresa_id or not filial_id:
        messages.error(request, "Sessão inválida: empresa/filial não informadas.")
        return redirect("PisosWeb:orcamentos_pisos_listar", slug=slug)
    if empresa_id is not None:
        try:
            qs = qs.filter(orca_empr=int(empresa_id))
        except Exception:
            qs = qs.filter(orca_empr=empresa_id)
    if filial_id is not None:
        try:
            qs = qs.filter(orca_fili=int(filial_id))
        except Exception:
            qs = qs.filter(orca_fili=filial_id)

    # Buscar sempre dentro da empresa/filial logada
    try:
        orcamento = get_object_or_404(qs, orca_nume=numero)
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
                    [current_date, current_date, numero]
                )

            # Retry the query after fixing
            orcamento = get_object_or_404(qs, orca_nume=numero)
        raise

    try:
        pedido_numero = OrcamentoExportarPedidoService().executar(
            banco=banco,
            empresa=orcamento.orca_empr,
            filial=orcamento.orca_fili,
            numero=orcamento.orca_nume,
        )

        messages.success(
            request,
            f"Orçamento {numero} exportado para pedido {pedido_numero}."
        )

        return redirect(
            "PisosWeb:pedidos_pisos_visualizar",
            slug=slug,
            pk=pedido_numero,
        )

    except Exception as exc:
        logger.exception(
            "Erro ao exportar orçamento para pedido (slug=%s, banco=%s, orca=%s).",
            slug,
            banco,
            numero,
        )

        messages.error(request, f"Erro ao exportar orçamento: {exc}")

        return redirect(
            "PisosWeb:orcamentos_pisos_visualizar",
            slug=slug,
            pk=numero,
        )
