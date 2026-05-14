from dataclasses import dataclass
from decimal import Decimal
from itertools import product
from typing import Iterable, Optional

from django.db import transaction

from ..models_tributos import Tributos


@dataclass
class TributoSpartacusAdapter:
    origem: Tributos
    fonte: str = "SPARTACUS"

    @property
    def uf_origem(self):
        return None

    @property
    def uf_destino(self):
        return (getattr(self.origem, "trib_esta", None) or "").strip().upper() or None

    @property
    def tipo_entidade(self):
        return (getattr(self.origem, "trib_enti", None) or "").strip().upper() or None

    @property
    def cst_icms(self):
        return getattr(self.origem, "trib_cst_icms", None)

    @property
    def cst_ipi(self):
        return None

    @property
    def cst_pis(self):
        return getattr(self.origem, "trib_cst_pis", None)

    @property
    def cst_cofins(self):
        return getattr(self.origem, "trib_cst_cofi", None)

    @property
    def cst_cbs(self):
        return None

    @property
    def cst_ibs(self):
        return None

    @property
    def aliq_icms(self):
        return getattr(self.origem, "trib_aliq_icms", None)

    @property
    def aliq_ipi(self):
        return None

    @property
    def aliq_pis(self):
        return getattr(self.origem, "trib_aliq_pis", None)

    @property
    def aliq_cofins(self):
        return getattr(self.origem, "trib_aliq_cofi", None)

    @property
    def aliq_cbs(self):
        return None

    @property
    def aliq_ibs(self):
        return None

    @property
    def aliq_icms_st(self):
        return getattr(self.origem, "trib_aliq_icms_st", None)

    @property
    def redu_icms(self):
        return getattr(self.origem, "trib_redu_icms", None)

    @property
    def redu_icms_st(self):
        return getattr(self.origem, "trib_redu_icms_st", None)

    @property
    def mva_icms_st(self):
        return getattr(self.origem, "trib_mva_icms_st", None)

    @property
    def cfop(self):
        return getattr(self.origem, "trib_cfop", None)

    @property
    def redu_base(self):
        return getattr(self.origem, "trib_redu_base", None)


class TributoService:
    ENTIDADE_ALIAS_MAP = {
        "CL": "000",
        "AM": "000",
        "FO": "011",
        "OU": "011",
        "VE": "011",
        "FU": "011",
    }

    def __init__(self, banco: str, empresa: int, filial: int):
        self.banco = banco or "default"
        self.empresa = self._to_int(empresa)
        self.filial = self._to_int(filial)

    def _qs(self):
        return Tributos.objects.using(self.banco)

    def _to_int(self, valor):
        try:
            return int(valor)
        except Exception:
            return valor

    def _to_decimal(self, valor) -> Optional[Decimal]:
        if valor in (None, ""):
            return None
        if isinstance(valor, Decimal):
            return valor
        return Decimal(str(valor))

    def _normalize_codigo(self, codigo: str) -> str:
        return str(codigo or "").strip()

    def _normalize_tipo(self, tipo: str) -> str:
        return str(tipo or "P").strip().upper()[:1] or "P"

    def _normalize_estado(self, estado: str) -> str:
        return str(estado or "").strip().upper()

    def _normalize_entidade(self, entidade: str) -> str:
        return str(entidade or "").strip().upper()

    def _entity_candidates(self, entidade: Optional[str]) -> list[str]:
        raw = self._normalize_entidade(entidade)
        candidates = []
        if raw:
            candidates.append(raw)
            alias = self.ENTIDADE_ALIAS_MAP.get(raw)
            if alias and alias not in candidates:
                candidates.append(alias)
        if "000" not in candidates:
            candidates.append("000")
        return candidates

    def _matches_entity(self, tributo: Tributos, candidates: list[str]) -> bool:
        if not candidates:
            return True
        return self._normalize_entidade(getattr(tributo, "trib_enti", None)) in candidates

    def _score(self, tributo: Tributos, estado: Optional[str], candidates: list[str]) -> int:
        score = 0
        trib_estado = self._normalize_estado(getattr(tributo, "trib_esta", None))
        trib_entidade = self._normalize_entidade(getattr(tributo, "trib_enti", None))

        if estado and trib_estado == estado:
            score += 20

        if trib_entidade in candidates:
            score += max(1, 10 - candidates.index(trib_entidade))

        if trib_entidade == "000":
            score += 1

        return score

    def listar(self, codigo: str, tipo: str = "P"):
        codigo = self._normalize_codigo(codigo)
        tipo = self._normalize_tipo(tipo)
        if not codigo:
            return self._qs().none()
        return self._qs().filter(
            trib_empr=self.empresa,
            trib_fili=self.filial,
            trib_tipo=tipo,
            trib_codi=codigo,
        ).order_by("trib_esta", "trib_enti")

    def buscar(self, trib_codi: str, estado: str = None, entidade: str = None, tipo: str = "P") -> Tributos:
        return self.buscar_contexto(
            codigo=trib_codi,
            estado=estado,
            entidade=entidade,
            tipo=tipo,
        )

    def buscar_contexto(self, codigo: str, estado: str = None, entidade: str = None, tipo: str = "P") -> Tributos:
        estado = self._normalize_estado(estado)
        candidates = self._entity_candidates(entidade)

        rows = list(self.listar(codigo=codigo, tipo=tipo))
        if estado:
            rows = [row for row in rows if self._normalize_estado(row.trib_esta) == estado]
        if not rows:
            return None

        filtrados = [row for row in rows if self._matches_entity(row, candidates)]
        if filtrados:
            rows = filtrados

        rows.sort(key=lambda row: self._score(row, estado, candidates), reverse=True)
        return rows[0] if rows else None

    def to_adapter(self, tributo: Tributos) -> TributoSpartacusAdapter | None:
        if not tributo:
            return None
        return TributoSpartacusAdapter(origem=tributo)

    def _defaults_from_data(self, dados: dict) -> dict:
        return {
            "trib_aliq_icms": self._to_decimal(dados["icms"]["aliquota"]),
            "trib_redu_icms": self._to_decimal(dados["icms"]["reducao"]),
            "trib_cst_icms": dados["icms"]["cst"] or None,
            "trib_aliq_icms_st": self._to_decimal(dados["icms_st"]["aliquota"]),
            "trib_redu_icms_st": self._to_decimal(dados["icms_st"]["reducao"]),
            "trib_mva_icms_st": self._to_decimal(dados["icms_st"]["mva"]),
            "trib_cst_pis": dados["pis"]["cst"] or None,
            "trib_aliq_pis": self._to_decimal(dados["pis"]["aliquota"]),
            "trib_cst_cofi": dados["cofins"]["cst"] or None,
            "trib_aliq_cofi": self._to_decimal(dados["cofins"]["aliquota"]),
            "trib_cfop": self._to_int(dados["cfop"]) if dados["cfop"] not in (None, "") else None,
        }

    def salvar(self, dados: dict) -> Tributos:
        tipo = self._normalize_tipo(dados["tipo"])
        entidade = self._normalize_entidade(dados["entidade"])
        estado = self._normalize_estado(dados["estado"])
        codigo = self._normalize_codigo(dados["codigo"])

        obj, _ = self._qs().update_or_create(
            trib_empr=self.empresa,
            trib_fili=self.filial,
            trib_tipo=tipo,
            trib_enti=entidade,
            trib_esta=estado,
            trib_codi=codigo,
            defaults=self._defaults_from_data(dados),
        )
        return obj

    def excluir(self, *, codigo: str, estado: str, entidade: str, tipo: str = "P") -> int:
        qs = self._qs().filter(
            trib_empr=self.empresa,
            trib_fili=self.filial,
            trib_tipo=self._normalize_tipo(tipo),
            trib_codi=self._normalize_codigo(codigo),
            trib_esta=self._normalize_estado(estado),
            trib_enti=self._normalize_entidade(entidade),
        )
        deleted, _ = qs.delete()
        return deleted

    def clonar(
        self,
        *,
        codigo: str,
        origem_estado: str,
        origem_entidade: str,
        estados_destino: Iterable[str],
        entidades_destino: Iterable[str],
        tipo: str = "P",
        codigo_destino: str = None,
    ) -> list[Tributos]:
        tipo = self._normalize_tipo(tipo)
        codigo = self._normalize_codigo(codigo)
        codigo_destino = self._normalize_codigo(codigo_destino or codigo)
        origem_estado = self._normalize_estado(origem_estado)
        origem_entidade = self._normalize_entidade(origem_entidade)

        estados = [self._normalize_estado(x) for x in (estados_destino or []) if self._normalize_estado(x)]
        entidades = [self._normalize_entidade(x) for x in (entidades_destino or []) if self._normalize_entidade(x)]
        if not estados:
            estados = [origem_estado]
        if not entidades:
            entidades = [origem_entidade]

        origem = self._qs().filter(
            trib_empr=self.empresa,
            trib_fili=self.filial,
            trib_tipo=tipo,
            trib_codi=codigo,
            trib_esta=origem_estado,
            trib_enti=origem_entidade,
        ).first()
        if not origem:
            return []

        payload_base = {
            "tipo": tipo,
            "codigo": codigo_destino,
            "icms": {
                "aliquota": origem.trib_aliq_icms,
                "reducao": origem.trib_redu_icms,
                "cst": origem.trib_cst_icms,
            },
            "icms_st": {
                "aliquota": origem.trib_aliq_icms_st,
                "reducao": origem.trib_redu_icms_st,
                "mva": origem.trib_mva_icms_st,
            },
            "pis": {
                "cst": origem.trib_cst_pis,
                "aliquota": origem.trib_aliq_pis,
            },
            "cofins": {
                "cst": origem.trib_cst_cofi,
                "aliquota": origem.trib_aliq_cofi,
            },
            "cfop": origem.trib_cfop,
        }

        criados = []
        with transaction.atomic(using=self.banco):
            for estado_destino, entidade_destino in product(estados, entidades):
                payload = {
                    **payload_base,
                    "estado": estado_destino,
                    "entidade": entidade_destino,
                }
                criados.append(self.salvar(payload))
        return criados
