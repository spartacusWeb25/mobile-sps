# views/calcular_item_view.py
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from Produtos.models import Produtos
from Pisos.services.calculo_services import calcular_item
from Pisos.services.preco_service import get_preco_produto
from Pisos.services.utils_service import parse_decimal, arredondar
from core.utils import get_db_from_slug

@require_POST
def api_calcular_item(request, slug):
    banco = get_db_from_slug(slug)
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"erro": "JSON inválido"}, status=400)

    class ItemProxy:
        item_m2 = body.get("item_m2") or 0
        item_queb = body.get("item_queb") or 0
        item_unit = body.get("item_unit") or 0

    prod_id = body.get("item_prod")
    condicao = str(body.get("condicao") or "0").strip()
    produto = None
    if prod_id:
        produto = Produtos.objects.using(banco).filter(prod_codi=prod_id).first()

    resultado = calcular_item(ItemProxy(), produto=produto)

    def _normalizar_unidade(produto_obj):
        if not produto_obj:
            return None
        un = getattr(produto_obj, "prod_unme", None)
        if un is None:
            return None
        codigo = getattr(un, "unid_codi", None) or getattr(un, "unid_desc", None) or str(un)
        codigo = str(codigo).strip().upper()
        if codigo in {"METRO QUADRADO", "M²", "M2", "MT2", "M"}:
            return "M2"
        if codigo in {"PEÇA", "PECA", "PÇ", "PC", "UN", "UNIDADE"}:
            return "PC"
        return codigo or None

    caixas = parse_decimal(resultado.get("caixas_necessarias") or 0)
    m2_por_caixa = parse_decimal(resultado.get("m2_por_caixa") or 0)
    pc_por_caixa = parse_decimal(resultado.get("pc_por_caixa") or 0)
    metragem_com_perda = parse_decimal(resultado.get("metragem_com_perda") or 0)
    metragem_real = parse_decimal(resultado.get("metragem_real") or 0)
    preco_unit = parse_decimal(body.get("item_unit") or 0)
    if prod_id and preco_unit <= 0:
        try:
            preco_unit = get_preco_produto(banco, prod_id, condicao)
        except Exception:
            preco_unit = parse_decimal(getattr(produto, "prod_prec", 0) if produto else 0)

    unidade = _normalizar_unidade(produto)
    if unidade == "M2":
        quantidade = (caixas * m2_por_caixa) if (caixas > 0 and m2_por_caixa > 0) else metragem_com_perda
    elif unidade == "PC":
        quantidade = (caixas * pc_por_caixa) if (caixas > 0 and pc_por_caixa > 0) else metragem_real
    else:
        quantidade = metragem_real

    total = quantidade * preco_unit

    return JsonResponse({
        "caixas": str(int(caixas) if caixas is not None else 0),
        "quantidade": str(arredondar(quantidade, 2)),
        "total": str(arredondar(total, 2)),
        "preco_unitario": str(arredondar(preco_unit, 2)),
        "m2_por_caixa": str(arredondar(m2_por_caixa, 2)),
        "pc_por_caixa": str(arredondar(pc_por_caixa, 2)),
    })
