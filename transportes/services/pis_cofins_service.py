from decimal import Decimal
from transportes.models import RegraPISCOFINS
from django.db.models import Q
import logging
import time


class PISCOFINSService:
    def __init__(self, cte, empresa, cfop, operacao, slug=None):
        self.cte = cte
        self.empresa = empresa
        self.cfop = cfop
        self.operacao = operacao
        self.db_alias = slug or cte._state.db or "default"

    def calcular(self, base_calculo):
        regra = self._buscar_regra()
        if not regra:
            return None

        base = Decimal(base_calculo or 0)

        valor_pis = base * (regra.pis_aliquota / Decimal("100"))
        valor_cofins = base * (regra.cofins_aliquota / Decimal("100"))

        return {
            "cst_pis": regra.pis_cst,
            "base_pis": round(base, 2),
            "aliquota_pis": regra.pis_aliquota,
            "valor_pis": round(valor_pis, 2),

            "cst_cofins": regra.cofins_cst,
            "base_cofins": round(base, 2),
            "aliquota_cofins": regra.cofins_aliquota,
            "valor_cofins": round(valor_cofins, 2),
        }

    def _buscar_regra(self):
        t0 = time.perf_counter()
        uf_origem = (getattr(self.operacao, "uf_origem", None) or "").strip() or None
        uf_destino = (getattr(self.operacao, "uf_destino", None) or "").strip() or None

        qs = RegraPISCOFINS.objects.using(self.db_alias).filter(
            empresa=self.cte.empresa,
            simples_nacional=getattr(self.empresa, "simples_nacional", False),
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
                    "PISCOFINSService.regra match=cfop regra_id=%s cfop=%s uf=%s->%s simples=%s ms=%.2f",
                    getattr(regra_cfop, "pk", None),
                    getattr(self.cfop, "cfop_codi", None),
                    uf_origem,
                    uf_destino,
                    getattr(self.empresa, "simples_nacional", None),
                    (time.perf_counter() - t0) * 1000,
                )
                return regra_cfop

        regra_geral = qs.filter(cfop__isnull=True).first() or qs.filter(cfop="").first()
        logging.getLogger(__name__).info(
            "PISCOFINSService.regra match=%s regra_id=%s cfop=%s uf=%s->%s simples=%s ms=%.2f",
            "geral" if regra_geral else "nenhuma",
            getattr(regra_geral, "pk", None) if regra_geral else None,
            getattr(self.cfop, "cfop_codi", None) if self.cfop else None,
            uf_origem,
            uf_destino,
            getattr(self.empresa, "simples_nacional", None),
            (time.perf_counter() - t0) * 1000,
        )
        return regra_geral
