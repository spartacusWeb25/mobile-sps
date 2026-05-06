from transportes.models import RegraICMS
from CFOP.models import CFOP
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class ICMSCalculationService:

    def __init__(self, empresa, operacao):
        self.empresa = empresa
        self.operacao = operacao

    def calcular(self, base_calculo, cfop: CFOP):
        if not cfop:
            return None

        regra = self._buscar_regra(cfop)
        if not regra:
             # Se não achar regra, retorna None ou levanta erro?
             # Por enquanto retorna None, o usuário terá que preencher manual
             return None

        if regra.isento:
            return {
                "cst": "90" if regra.simples_nacional else regra.cst,
                "base": Decimal(0),
                "aliquota": Decimal(0),
                "valor": Decimal(0),
                "reducao": Decimal(0)
            }
        
        # Converte para Decimal para evitar erros de precisão
        base = Decimal(base_calculo)
        aliquota = regra.aliquota
        reducao = regra.reducao_base
        
        base_reduzida = base
        if reducao:
            base_reduzida = base * (1 - reducao / 100)

        valor_icms = base_reduzida * (aliquota / 100)

        return {
            "cst": "90" if regra.simples_nacional else regra.cst,
            "base": round(base_reduzida, 2),
            "aliquota": aliquota,
            "valor": round(valor_icms, 2),
            "reducao": reducao
        }

    def _buscar_regra(self, cfop):
        # Garante uso do banco correto
        db_alias = self.empresa._state.db or 'default'
        
        uf_origem = getattr(self.operacao, "uf_origem", None)
        uf_destino = getattr(self.operacao, "uf_destino", None)
        contribuinte = bool(getattr(self.operacao, "contribuinte", False))
        simples = bool(getattr(self.empresa, "simples_nacional", False))

        base_qs = RegraICMS.objects.using(db_alias).filter(
            uf_origem=uf_origem,
            uf_destino=uf_destino,
        )

        def pick(qs):
            obj = qs.filter(cfop=cfop.cfop_codi).first()
            if obj:
                return obj
            obj = qs.filter(cfop__isnull=True).first()
            if obj:
                return obj
            return qs.filter(cfop="").first()

        # 1) Match exato (contribuinte + simples)
        r = pick(base_qs.filter(contribuinte=contribuinte, simples_nacional=simples))
        if r:
            return r

        # 2) Fallback ignorando contribuinte (mantém simples)
        r = pick(base_qs.filter(simples_nacional=simples))
        if r:
            return r

        # 3) Fallback ignorando simples (mantém contribuinte)
        r = pick(base_qs.filter(contribuinte=contribuinte))
        if r:
            return r

        # 4) Fallback geral (somente UF)
        r = pick(base_qs)
        if r:
            return r

        logger.info(
            "ICMSCalculationService.regra_nao_encontrada cfop=%s uf=%s->%s contrib=%s simples=%s",
            getattr(cfop, "cfop_codi", None),
            uf_origem,
            uf_destino,
            contribuinte,
            simples,
        )
        return None
