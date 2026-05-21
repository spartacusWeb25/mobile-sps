"""
Pisos/views/pedido_emitir_nfe_view.py

View responsável apenas por:
  - Receber o request (GET = emissão total, POST = emissão parcial com JSON de itens)
  - Carregar o pedido
  - Chamar PedidoEmitirNFeService
  - Exibir mensagem e redirecionar

Toda a lógica de negócio fica em PedidoEmitirNFeService.
"""

import json
import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from core.utils import get_licenca_db_config

from Pisos.models import Pedidospisos
from Pisos.services.pedido_emitir_nfe_service import PedidoEmitirNFeService

logger = logging.getLogger(__name__)


class PedidoPisosEmitirNFeView(View):
    """
    GET  /web/<slug>/pisos/pedidos/<pk>/emitir-nfe/
        → emite todos os itens com saldo pendente (emissão total ou complementar).

    POST /web/<slug>/pisos/pedidos/<pk>/emitir-nfe/
        Body JSON (ou form field "itens_emitir"):
        [
            {"item_nume": 1, "quantidade": 5},
            {"item_nume": 3, "quantidade": 2}
        ]
        → emissão parcial com as quantidades informadas.
    """

    redirect_url_name = "pisos:pedidos_lista"   # ajuste para o name correto da sua url

    def _redirect(self, slug: str):
        return redirect(f"/web/{slug}/pisos/pedidos/")

    # ------------------------------------------------------------------

    def get(self, request, slug, pk):
        if request.headers.get("Accept", "").find("application/json") >= 0 or request.path.endswith("/nfe-itens/"):
            return self._itens_json(request, slug, pk)
        return self._processar(request, slug, pk, itens_emitir=None)

    def post(self, request, slug, pk):
        itens_emitir = self._parse_itens(request)
        return self._processar(request, slug, pk, itens_emitir=itens_emitir)

    def _itens_json(self, request, slug, pk):
        banco = get_licenca_db_config(request) or "default"
        empresa_id = int(request.session.get("empresa_id", 1))
        filial_id = int(request.session.get("filial_id", 1))

        pedido = get_object_or_404(
            Pedidospisos.objects.using(banco).filter(
                pedi_empr=empresa_id,
                pedi_fili=filial_id,
            ),
            pedi_nume=int(pk),
        )

        from Pisos.services.pedido_emitir_nfe_service import PedidoEmitirNFeService

        service = PedidoEmitirNFeService(
            banco=banco,
            pedido=pedido,
            empresa=empresa_id,
            filial=filial_id,
        )
        dados = service.listar_itens_nfe()
        return JsonResponse({"ok": True, **dados})

    # ------------------------------------------------------------------

    def _processar(self, request, slug, pk, itens_emitir):
        banco = get_licenca_db_config(request) or "default"
        empresa_id = int(request.session.get("empresa_id", 1))
        filial_id = int(request.session.get("filial_id", 1))

        pedido = get_object_or_404(
            Pedidospisos.objects.using(banco).filter(
                pedi_empr=empresa_id,
                pedi_fili=filial_id,
            ),
            pedi_nume=int(pk),
        )

        try:
            service = PedidoEmitirNFeService(
                banco=banco,
                pedido=pedido,
                empresa=empresa_id,
                filial=filial_id,
            )

            resultado = service.emitir(itens_emitir=itens_emitir)
            sefaz = resultado.get("sefaz", {})
            status = str(sefaz.get("status", ""))

            if status in ("100", "204"):
                chave = sefaz.get("chave", "")
                msg = f"NF-e autorizada! Chave: {chave}"
                if status == "204":
                    msg = f"NF-e autorizada (duplicidade SEFAZ). Chave: {chave}"
                messages.success(request, msg)
            else:
                messages.warning(
                    request,
                    f"Rejeição SEFAZ: {status} — {sefaz.get('motivo', '')}",
                )

        except ValidationError as exc:
            # Erros de validação de negócio (saldo insuficiente, item inválido…)
            detail = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            messages.error(request, f"Erro de validação: {detail}")
            logger.warning("Validação ao emitir NF-e pedido %s: %s", pk, detail)

        except Exception as exc:
            messages.error(request, f"Erro ao emitir NF-e: {exc}")
            logger.exception("Erro inesperado ao emitir NF-e pedido %s", pk)

        return self._redirect(slug)

    # ------------------------------------------------------------------

    @staticmethod
    def _parse_itens(request) -> list[dict] | None:
        """
        Tenta extrair itens_emitir do body.
        Aceita tanto JSON puro no body quanto form-field 'itens_emitir'.
        Retorna None se não encontrar nada (aciona emissão total).
        """
        # 1) JSON puro no body
        content_type = request.content_type or ""
        if "application/json" in content_type:
            try:
                data = json.loads(request.body)
                if isinstance(data, list):
                    return data
                return data.get("itens_emitir")
            except (json.JSONDecodeError, AttributeError):
                return None

        # 2) form field
        raw = request.POST.get("itens_emitir")
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None

        return None
