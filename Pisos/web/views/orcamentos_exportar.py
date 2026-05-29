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

    mix = VendedorEntidadeMixin()
    mix.request = request
    qs = mix.filter_por_vendedor(Orcamentopisos.objects.using(banco), 'orca_vend')

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

    orcamento = get_object_or_404(qs, orca_nume=numero)

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
