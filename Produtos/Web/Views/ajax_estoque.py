import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.utils import get_licenca_db_config
from Produtos.services.estoque_movimentacao_service import EstoqueMovimentacaoService


@require_POST
def ajax_movimentar_estoque(request, slug=None):
    banco = get_licenca_db_config(request) or "default"
    empresa_id = request.session.get("empresa_id") or request.headers.get("X-Empresa")
    filial_id = request.session.get("filial_id") or request.headers.get("X-Filial") or 1
    usuario_id = request.session.get("usua_codi") or 0

    if not empresa_id:
        return JsonResponse({"detail": "Empresa não informada."}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}") or {}
    except Exception:
        payload = {}

    tipo = (payload.get("tipo") or "").strip().upper()
    produto = (payload.get("produto") or payload.get("prod_codi") or "").strip()
    quantidade = payload.get("quantidade") or payload.get("quan") or payload.get("qtd")
    total = payload.get("total") or payload.get("tota") or 0
    entidade = (payload.get("entidade") or "").strip() or None
    observacao = (payload.get("observacao") or payload.get("obs") or "").strip()
    data = (payload.get("data") or "").strip() or None

    if not produto:
        return JsonResponse({"detail": "Produto não informado."}, status=400)

    try:
        if tipo == "ENTRADA":
            result = EstoqueMovimentacaoService.registrar_entrada(
                banco,
                empresa_id=empresa_id,
                filial_id=filial_id,
                produto_codigo=produto,
                quantidade=quantidade,
                total=total,
                entidade=entidade,
                observacao=observacao,
                data=data,
                usuario_id=usuario_id,
            )
        elif tipo == "SAIDA":
            result = EstoqueMovimentacaoService.registrar_saida(
                banco,
                empresa_id=empresa_id,
                filial_id=filial_id,
                produto_codigo=produto,
                quantidade=quantidade,
                total=total,
                entidade=entidade,
                observacao=observacao,
                data=data,
                usuario_id=usuario_id,
            )
        else:
            return JsonResponse({"detail": "Tipo inválido. Use ENTRADA ou SAIDA."}, status=400)
    except Exception as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    return JsonResponse({"ok": True, "resultado": result})

