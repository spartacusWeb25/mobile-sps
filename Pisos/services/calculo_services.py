# services/calculo_service.py
from .utils_service import parse_decimal, arredondar
from decimal import Decimal, ROUND_HALF_UP
import math
from collections import defaultdict

def calcular_item(item, produto=None):
    metragem = parse_decimal(item.item_m2 or 0)
    perda = parse_decimal(item.item_queb or 0) / Decimal(100)
    preco_unit = parse_decimal(item.item_unit or 0)

    m2_por_caixa = parse_decimal(getattr(produto, "prod_cera_m2cx", 0) or 0)
    pc_por_caixa = parse_decimal(getattr(produto, "prod_cera_pccx", 0) or 0)
    kg_por_caixa = parse_decimal(getattr(produto, "prod_cera_kgcx", 0) or 0)

    tem_caixa = m2_por_caixa > 0
    tem_pc = pc_por_caixa > 0
    tem_kg = kg_por_caixa > 0

    metragem_com_perda = metragem * (Decimal(1) + perda)

    if tem_caixa:
        caixas_necessarias = math.ceil(metragem_com_perda / m2_por_caixa)
        metragem_real = Decimal(caixas_necessarias) * m2_por_caixa
    elif tem_pc:
        caixas_necessarias = math.ceil(metragem_com_perda / pc_por_caixa)
        metragem_real = Decimal(caixas_necessarias) * pc_por_caixa
    else:
        caixas_necessarias = None
        metragem_real = metragem_com_perda

    quilos_total = None
    if tem_kg:
        base_kg = Decimal(caixas_necessarias) if caixas_necessarias is not None else metragem_com_perda
        quilos_total = base_kg * kg_por_caixa

    total = metragem_real * preco_unit
    return {
        "metragem_com_perda": arredondar(metragem_com_perda, 2),
        "caixas_necessarias": caixas_necessarias,
        "metragem_real": arredondar(metragem_real, 2),
        "total": arredondar(total),

        "m2_por_caixa": arredondar(m2_por_caixa, 2) if tem_caixa else None,
        "pc_por_caixa": arredondar(pc_por_caixa, 2) if tem_pc else None,
        "kg_por_caixa": arredondar(kg_por_caixa, 2) if tem_kg else None,
        "quilos_total": arredondar(quilos_total, 2) if quilos_total is not None else None,

        "tem_caixa": tem_caixa,
        "tem_pc": tem_pc,
        "tem_kg": tem_kg,
        
    }
    


def calcular_ambientes(itens):
    """Agrupa itens por ambiente e soma totais.
    Usa o subtotal já calculado (item_suto) para evitar recálculos incorretos.
    """
    agrupado = defaultdict(lambda: {"total": Decimal("0.00"), "m2_total": Decimal("0.00"), "count": 0})

    for item in itens:
        amb = item.item_ambi or 0
        if not amb:
            amb = 1
        # Usar o subtotal já calculado (item_suto) em vez de recalcular
        item_subtotal = parse_decimal(getattr(item, 'item_suto', 0))
        item_m2 = parse_decimal(getattr(item, 'item_m2', 0))
        
        agrupado[amb]["total"] += item_subtotal
        agrupado[amb]["m2_total"] += item_m2
        agrupado[amb]["count"] += 1

    return [
        {
            "ambiente": amb,
            "total_ambiente": arredondar(data["total"]),
            "m2_total": arredondar(data["m2_total"], 2),
            "qtd_itens": data["count"]
        }
        for amb, data in agrupado.items()
    ]

def calcular_total_geral(ambientes):
    """Soma todos os ambientes."""
    return sum(parse_decimal(amb["total_ambiente"]) for amb in ambientes)

