# transportes/services/fiscal_cte_service.py

from decimal import Decimal
import logging
import time

from CFOP.models import CFOP
from transportes.services.icms_service import ICMSCalculationService
from transportes.services.pis_cofins_service import PISCOFINSService
from transportes.services.ibs_cbs_service import IBSCBSService
from transportes.services.difal_service import DIFALService
from transportes.services.st_service import STService

logger = logging.getLogger(__name__)


class FiscalCTeService:
    def __init__(self, cte, empresa, operacao, slug=None, db_alias=None):
        self.cte = cte
        self.empresa = empresa
        self.operacao = operacao
        self.slug = slug
        self.db_alias = db_alias or slug or cte._state.db or "default"

    def calcular(self, cfop=None):
        t0 = time.perf_counter()
        cfop = cfop or self._get_cfop()
        base = self._get_base_calculo()

        logger.info(
            "FiscalCTeService.calcular cte_id=%s cfop=%s uf=%s->%s simples=%s contrib=%s base=%s",
            getattr(self.cte, "pk", None),
            getattr(cfop, "cfop_codi", None),
            getattr(self.operacao, "uf_origem", None),
            getattr(self.operacao, "uf_destino", None),
            getattr(self.empresa, "simples_nacional", None),
            getattr(self.operacao, "contribuinte", None),
            base,
        )

        response_data = {}

        t_icms = time.perf_counter()
        icms = ICMSCalculationService(self.empresa, self.operacao).calcular(base, cfop)
        if icms:
            response_data.update({
                "cst_icms": icms["cst"],
                "base_icms": icms["base"],
                "aliq_icms": icms["aliquota"],
                "valor_icms": icms["valor"],
                "reducao_icms": icms["reducao"],
            })
        elif cfop:
            response_data.update({
                "base_icms": round(Decimal(base or 0), 2),
                "aliq_icms": Decimal("0.00"),
                "valor_icms": Decimal("0.00"),
                "reducao_icms": Decimal("0.00"),
            })
        logger.info("FiscalCTeService.icms ms=%.2f found=%s", (time.perf_counter() - t_icms) * 1000, bool(icms))

        icms_valor = Decimal("0.00")
        try:
            icms_valor = Decimal(str(response_data.get("valor_icms") or "0"))
        except Exception:
            icms_valor = Decimal("0.00")

        t_st = time.perf_counter()
        st = STService(self.empresa, self.operacao).calcular(
            base,
            icms_valor,
            cfop
        )
        if st:
            response_data.update({
                "base_icms_st": st["base_st"],
                "valor_icms_st": st["valor_st"],
                "aliquota_icms_st": st["aliquota_st"],
                "margem_valor_adicionado_st": st["mva_st"],
            })
        elif cfop:
            response_data.update({
                "base_icms_st": Decimal("0.00"),
                "valor_icms_st": Decimal("0.00"),
                "aliquota_icms_st": Decimal("0.00"),
                "margem_valor_adicionado_st": Decimal("0.00"),
            })
        logger.info("FiscalCTeService.st ms=%.2f found=%s", (time.perf_counter() - t_st) * 1000, bool(st))

        t_difal = time.perf_counter()
        difal = DIFALService(self.empresa, self.operacao).calcular(
            base,
            icms_valor,
            cfop
        )
        if difal:
            response_data.update({
                "valor_bc_uf_dest": difal["base_difal"],
                "valor_icms_uf_dest": difal["valor_difal"],
                "aliquota_interestadual": difal["aliquota_interestadual"],
                "aliquota_interna_dest": difal["aliquota_destino"],
            })
        elif cfop:
            response_data.update({
                "valor_bc_uf_dest": round(Decimal(base or 0), 2),
                "valor_icms_uf_dest": Decimal("0.00"),
                "aliquota_interestadual": Decimal("0.00"),
                "aliquota_interna_dest": Decimal("0.00"),
            })
        logger.info("FiscalCTeService.difal ms=%.2f found=%s", (time.perf_counter() - t_difal) * 1000, bool(difal))
        
        t_pis = time.perf_counter()
        pis_cofins = PISCOFINSService(
            cte=self.cte,
            empresa=self.empresa,
            cfop=cfop,
            operacao=self.operacao,
            slug=self.slug,
        ).calcular(base)

        if pis_cofins:
            response_data.update(pis_cofins)
        logger.info("FiscalCTeService.pis_cofins ms=%.2f found=%s", (time.perf_counter() - t_pis) * 1000, bool(pis_cofins))

        t_ibs = time.perf_counter()
        ibs_cbs = IBSCBSService(
            cte=self.cte,
            cfop=cfop,
            operacao=self.operacao,
            slug=self.slug,
        ).calcular(base)

        if ibs_cbs:
            response_data.update(ibs_cbs)
        logger.info("FiscalCTeService.ibs_cbs ms=%.2f found=%s", (time.perf_counter() - t_ibs) * 1000, bool(ibs_cbs))

        logger.info("FiscalCTeService.total ms=%.2f", (time.perf_counter() - t0) * 1000)
        return response_data

    def aplicar(self, cfop=None):
        data = self.calcular(cfop=cfop)
        for campo, valor in data.items():
            setattr(self.cte, campo, valor)
        self.cte.save(using=self.db_alias)
        return self.cte

    def _get_cfop(self):
        if not self.cte.cfop:
            return None

        return (
            CFOP.objects
            .using(self.db_alias)
            .filter(cfop_codi=str(self.cte.cfop))
            .first()
        )

    def _get_base_calculo(self):
        return Decimal(
            self.cte.total_valor
            or self.cte.total_valor_liquido
            or self.cte.liquido_a_receber
            or 0
        )
