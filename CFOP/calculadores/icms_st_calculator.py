from decimal import Decimal
from .base_calculator import BaseCalculator


class ICMSSTCalculator(BaseCalculator):

    def _num(self, value):
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    def calcular(self, ctx, base, valor_icms_proprio):

        if base is None:
            return {
                "base": None,
                "aliquota": None,
                "valor": None,
                "cst": None
            }

        mva = ctx.icms_data.get("mva_st")
        aliq = ctx.icms_data.get("st_aliq")
        if getattr(ctx, "fiscal_padrao", None):
            mva_padrao = self._num(getattr(ctx.fiscal_padrao, "mva_icms_st", None))
            aliq_padrao = self._num(getattr(ctx.fiscal_padrao, "aliq_icms_st", None))
            if mva_padrao is not None:
                mva = mva_padrao
            if aliq_padrao is not None:
                aliq = aliq_padrao
        if not aliq:
            aliq = ctx.icms_data.get("icms")

        if not mva or not aliq:

            return {
                "base": None,
                "aliquota": None,
                "valor": None,
                "cst": None
            }

        base_st = base * (Decimal("1") + mva / self.D100)

        icms_total = base_st * aliq / self.D100

        valor_st = icms_total - (valor_icms_proprio or Decimal("0"))

        regime = str(getattr(ctx, "regime", "")).upper()
        is_simples = regime in {"1", "4", "SIMPLES", "MEI"}

        return {
            "base": self._d(base_st),
            "aliquota": aliq,
            "valor": self._d(valor_st),
            "cst": "500" if is_simples else "10"
        }
