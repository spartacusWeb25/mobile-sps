from decimal import Decimal
from ..services.bases import BaseFiscal


class BaseResolver:

    def _percent(self, value):
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    def _has_percent(self, value):
        return self._percent(value) is not None

    def resolver(self, ctx, base_raiz, valor_ipi):
        base_icms = base_raiz
        fiscal_padrao = getattr(ctx, "fiscal_padrao", None)

        redu_icms = self._percent(getattr(fiscal_padrao, "redu_icms", None))
        redu_base = getattr(fiscal_padrao, "redu_base", None)
        if redu_base and redu_icms:
            base_icms = base_raiz * (Decimal("1") - (redu_icms / Decimal("100")))

        if ctx.cfop and ctx.cfop.cfop_icms_base_inclui_ipi:
            base_icms += valor_ipi

        base_st = base_raiz
        redu_icms_st = self._percent(getattr(fiscal_padrao, "redu_icms_st", None))
        if redu_icms_st:
            base_st = base_st * (Decimal("1") - (redu_icms_st / Decimal("100")))

        if ctx.cfop and ctx.cfop.cfop_st_base_inclui_ipi:
            base_st += valor_ipi

        gera_st_por_padrao = bool(
            self._has_percent(getattr(fiscal_padrao, "aliq_icms_st", None))
            or self._has_percent(getattr(fiscal_padrao, "mva_icms_st", None))
        )

        if not ((ctx.cfop and ctx.cfop.cfop_gera_st) or gera_st_por_padrao):
            base_st = None

        return BaseFiscal(
            raiz=base_raiz,
            icms=base_icms,
            st=base_st,
            pis_cofins=base_raiz,
            cbs=base_raiz,
            ibs=base_raiz,
        )
