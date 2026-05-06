from decimal import Decimal
from transportes.models import RegraIBSCBS
from django.db.models import Q
import logging
import time


class IBSCBSService:
    def __init__(self, cte, cfop, operacao, slug=None):
        self.cte = cte
        self.cfop = cfop
        self.operacao = operacao
        self.db_alias = slug or cte._state.db or "default"

    def calcular(self, base_calculo):
        regra = self._buscar_regra()
        if not regra:
            return None

        base = Decimal(base_calculo or 0)

        aliq_cbs_efetiva = regra.aliquota_cbs * (1 - regra.reducao_cbs / Decimal("100"))
        aliq_ibs_uf_efetiva = regra.aliquota_ibs_uf * (1 - regra.reducao_ibs_uf / Decimal("100"))
        aliq_ibs_mun_efetiva = regra.aliquota_ibs_mun * (1 - regra.reducao_ibs_mun / Decimal("100"))

        valor_cbs = base * (aliq_cbs_efetiva / Decimal("100"))
        valor_ibs_uf = base * (aliq_ibs_uf_efetiva / Decimal("100"))
        valor_ibs_mun = base * (aliq_ibs_mun_efetiva / Decimal("100"))

        return {
            "ibscbs_vbc": round(base, 2),
            "ibscbs_cst": regra.cst,
            "ibscbs_cclasstrib": regra.cclasstrib,

            "cbs_pcbs": regra.aliquota_cbs,
            "cbs_pred": regra.reducao_cbs,
            "cbs_paliqefet": round(aliq_cbs_efetiva, 4),
            "cbs_vcbs": round(valor_cbs, 2),

            "ibs_pibsuf": regra.aliquota_ibs_uf,
            "ibs_preduf": regra.reducao_ibs_uf,
            "ibs_paliqefetuf": round(aliq_ibs_uf_efetiva, 4),
            "ibs_vibsuf": round(valor_ibs_uf, 2),

            "ibs_pibsmun": regra.aliquota_ibs_mun,
            "ibs_predmun": regra.reducao_ibs_mun,
            "ibs_paliqefetmun": round(aliq_ibs_mun_efetiva, 4),
            "ibs_vibsmun": round(valor_ibs_mun, 2),

            "ibs_vibs": round(valor_ibs_uf + valor_ibs_mun, 2),
        }

    def _buscar_regra(self):
        t0 = time.perf_counter()
        uf_origem = (getattr(self.operacao, "uf_origem", None) or "").strip() or None
        uf_destino = (getattr(self.operacao, "uf_destino", None) or "").strip() or None

        qs = RegraIBSCBS.objects.using(self.db_alias).filter(
            empresa=self.cte.empresa,
            ativo=True,
        )

        if uf_origem:
            qs = qs.filter(Q(uf_origem=uf_origem) | Q(uf_origem__isnull=True) | Q(uf_origem=""))

        if uf_destino:
            qs = qs.filter(Q(uf_destino=uf_destino) | Q(uf_destino__isnull=True) | Q(uf_destino=""))

        if self.cfop:
            regra_cfop = qs.filter(cfop=str(self.cfop.cfop_codi)).first()
            if regra_cfop:
                logging.getLogger(__name__).info(
                    "IBSCBSService.regra match=cfop regra_id=%s cfop=%s uf=%s->%s ms=%.2f",
                    getattr(regra_cfop, "pk", None),
                    getattr(self.cfop, "cfop_codi", None),
                    uf_origem,
                    uf_destino,
                    (time.perf_counter() - t0) * 1000,
                )
                return regra_cfop

        regra_geral = qs.filter(cfop__isnull=True).first() or qs.filter(cfop="").first()
        logging.getLogger(__name__).info(
            "IBSCBSService.regra match=%s regra_id=%s cfop=%s uf=%s->%s ms=%.2f",
            "geral" if regra_geral else "nenhuma",
            getattr(regra_geral, "pk", None) if regra_geral else None,
            getattr(self.cfop, "cfop_codi", None) if self.cfop else None,
            uf_origem,
            uf_destino,
            (time.perf_counter() - t0) * 1000,
        )
        return regra_geral
