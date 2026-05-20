from decimal import Decimal, ROUND_HALF_UP


class CalculoNfseService:
    @staticmethod
    def aplicar(data: dict) -> dict:
        payload = dict(data or {})

        itens = payload.get('itens') or []
        if itens and not payload.get('valor_servico'):
            total_itens = sum(Decimal(str(i.get('valor_total') or 0)) for i in itens)
            payload['valor_servico'] = total_itens

        valor_servico = Decimal(str(payload.get('valor_servico') or 0))
        valor_deducao = Decimal(str(payload.get('valor_deducao') or 0))
        valor_desconto = Decimal(str(payload.get('valor_desconto') or 0))
        valor_iss = Decimal(str(payload.get('valor_iss') or 0))
        aliquota_iss = Decimal(str(payload.get('aliquota_iss') or 0))
        base_iss = max(valor_servico - valor_deducao, Decimal('0.00'))

        if valor_iss <= 0 and aliquota_iss > 0 and base_iss > 0:
            valor_iss = (base_iss * (aliquota_iss / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            payload['valor_iss'] = valor_iss

        if aliquota_iss <= 0 and valor_iss > 0 and base_iss > 0:
            aliquota_iss = ((valor_iss / base_iss) * Decimal('100')).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            payload['aliquota_iss'] = aliquota_iss

        if not payload.get('valor_liquido'):
            payload['valor_liquido'] = (
                valor_servico
                - valor_deducao
                - valor_desconto
                - Decimal(str(payload.get('valor_iss') or 0))
                - Decimal(str(payload.get('valor_inss') or 0))
                - Decimal(str(payload.get('valor_irrf') or 0))
                - Decimal(str(payload.get('valor_csll') or 0))
                - Decimal(str(payload.get('valor_cofins') or 0))
                - Decimal(str(payload.get('valor_pis') or 0))
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return payload
