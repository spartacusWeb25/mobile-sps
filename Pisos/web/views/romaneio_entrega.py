import json
from json import JSONDecodeError

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from core.utils import get_db_from_slug
from Pisos.models import Pedidospisos
from Pisos.services.romaneio_entrega_service import RomaneioEntregaService


class RomaneioEntregaAjaxView(View):
    def get(self, request, slug, pk):
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

        itens = RomaneioEntregaService.listar_itens(
            banco=banco,
            pedido_numero=pedido.pedi_nume,
            empresa=getattr(pedido, "pedi_empr", None),
            filial=getattr(pedido, "pedi_fili", None),
        )

        return JsonResponse(
            {
                "ok": True,
                "pedido": int(pedido.pedi_nume),
                "pedi_obse_roma": (getattr(pedido, "pedi_obse_roma", "") or "").strip(),
                "itens": itens,
            }
        )

    def post(self, request, slug, pk):
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

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except JSONDecodeError:
            return JsonResponse({"ok": False, "erro": "JSON inválido."}, status=400)

        entregas = payload.get("entregas") or []
        pedido_observacao = payload.get("pedi_obse_roma", None)

        usuario_id = getattr(getattr(request, "user", None), "usua_codi", None)
        if not usuario_id:
            try:
                usuario_id = request.session.get("usua_codi")
            except Exception:
                usuario_id = None

        try:
            resumo = RomaneioEntregaService.entregar(
                banco=banco,
                pedido_numero=pedido.pedi_nume,
                empresa=getattr(pedido, "pedi_empr", None),
                filial=getattr(pedido, "pedi_fili", None),
                entregas=entregas,
                usuario_id=usuario_id,
                pedido_observacao=pedido_observacao,
            )
        except ValueError as e:
            return JsonResponse({"ok": False, "erro": str(e)}, status=400)
        except Exception:
            return JsonResponse({"ok": False, "erro": "Erro interno."}, status=500)

        itens = RomaneioEntregaService.listar_itens(
            banco=banco,
            pedido_numero=pedido.pedi_nume,
            empresa=getattr(pedido, "pedi_empr", None),
            filial=getattr(pedido, "pedi_fili", None),
        )

        pedido.refresh_from_db(using=banco, fields=["pedi_obse_roma"])

        return JsonResponse(
            {
                "ok": True,
                "resumo": resumo,
                "pedi_obse_roma": (getattr(pedido, "pedi_obse_roma", "") or "").strip(),
                "itens": itens,
            }
        )
