# service/clientes_sem_movimento.py

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import connections
from django.db.models import Q
from django.db.models import IntegerField, OuterRef
from django.db.models.functions import Cast

from Entidades.models import Entidades


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ids_int_str(ids: list) -> tuple[list[int], list[str]]:
    ints, strs = [], []
    for v in ids or []:
        if v in (None, ""):
            continue
        try:
            ints.append(int(v))
        except (TypeError, ValueError):
            pass
        try:
            strs.append(str(v))
        except Exception:
            pass
    return ints, strs


# ---------------------------------------------------------------------------
# Resultado tipado (simples, sem dataclass pesado)
# ---------------------------------------------------------------------------

class ClienteSemMovimentoRow:
    __slots__ = (
        "enti_clie", "enti_nome", "enti_empr", "enti_fili",
        "enti_vend", "enti_tipo_enti",
        "ultimo_pedido", "ultimo_orcamento",
        "ultimo_pedido_antes", "ultimo_orcamento_antes",
        "ultimo_pedido_antes_vend", "ultimo_orcamento_antes_vend",
        "tem_pedido_periodo", "tem_orcamento_periodo",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ClienteSemMovimentoService:
    def __init__(self, banco: str):
        self.banco = banco

    # ------------------------------------------------------------------
    # helpers internos
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_int(value):
        if value in (None, "", "None", "null", "undefined"):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_text(value):
        if value in (None, "", "None", "null", "undefined"):
            return None
        value = str(value).strip()
        return value or None

    # ------------------------------------------------------------------
    # ponto de entrada principal
    # ------------------------------------------------------------------

    def listar(
        self,
        *,
        empresa=None,
        filial=None,
        data_inicial: date | None = None,
        data_final: date | None = None,
        cliente_nome: str | None = None,
        vendedor_nome: str | None = None,
        vendedores_ids: list | None = None,
        somente_carteira: bool = False,
    ) -> list[ClienteSemMovimentoRow]:
        empresa = self._clean_int(empresa)
        filial = self._clean_int(filial)
        cliente_nome = self._clean_text(cliente_nome)
        vendedor_nome = self._clean_text(vendedor_nome)

        # resolve vendedor por nome se necessário
        if vendedores_ids is None and vendedor_nome:
            vendedores_ids = self._resolver_vendedores_por_nome(
                vendedor_nome, empresa
            )

        vend_int, vend_str = _ids_int_str(vendedores_ids or [])
        has_vendedor = bool(vend_int or vend_str)

        if vendedores_ids is not None and not has_vendedor:
            return []

        return self._executar_cte(
            empresa=empresa,
            filial=filial,
            data_inicial=data_inicial,
            data_final=data_final,
            cliente_nome=cliente_nome,
            vend_int=vend_int,
            vend_str=vend_str,
            has_vendedor=has_vendedor,
            somente_carteira=somente_carteira,
        )

    # ------------------------------------------------------------------
    # resolve vendedor por nome (uma única query ORM simples)
    # ------------------------------------------------------------------

    def _resolver_vendedores_por_nome(
        self, vendedor_nome: str, empresa: int | None
    ) -> list:
        if vendedor_nome.isdigit():
            return [int(vendedor_nome)]

        qs = Entidades.objects.using(self.banco).filter(
            enti_nome__icontains=vendedor_nome,
            enti_tipo_enti="VE",
        )
        if empresa:
            qs = qs.filter(enti_empr=empresa)

        return list(qs.values_list("enti_clie", flat=True)[:200])

    # ------------------------------------------------------------------
    # CTE principal
    # ------------------------------------------------------------------

    def _executar_cte(
        self,
        *,
        empresa: int | None,
        filial: int | None,
        data_inicial: date | None,
        data_final: date | None,
        cliente_nome: str | None,
        vend_int: list[int],
        vend_str: list[str],
        has_vendedor: bool,
        somente_carteira: bool,
    ) -> list[ClienteSemMovimentoRow]:

        PED_DATA = "COALESCE(p.pedi_data, p._log_data)"
        ORC_DATA = "COALESCE(o.orca_data, o._log_data)"

        params: dict[str, Any] = {}
        params.setdefault("data_inicial", data_inicial or date(1900, 1, 1))
        params.setdefault("data_final",   data_final   or date(9999, 12, 31))

        # ---------- WHERE pedidos/orçamentos ---------------------------------

        ped_where_parts = ["1=1"]
        orc_where_parts = ["1=1"]

        # sanitize: only consider pedidos/orçamentos from 2011-01-01 em diante
        params["min_year"] = date(2011, 1, 1)
        ped_where_parts.append("COALESCE(p.pedi_data, p._log_data) >= %(min_year)s")
        orc_where_parts.append("COALESCE(o.orca_data, o._log_data) >= %(min_year)s")

        if empresa:
            params["ped_empr"] = empresa
            params["orc_empr"] = empresa
            ped_where_parts.append("p.pedi_empr = %(ped_empr)s")
            orc_where_parts.append("o.orca_empr = %(orc_empr)s")

        if filial:
            params["ped_fili"] = filial
            params["orc_fili"] = filial
            ped_where_parts.append("p.pedi_fili = %(ped_fili)s")
            orc_where_parts.append("o.orca_fili = %(orc_fili)s")

        ped_where = " AND ".join(ped_where_parts)
        orc_where = " AND ".join(orc_where_parts)

        # ---------- cláusulas de vendedor nas CTEs ---------------------------

        def vend_clause(col: str, alias_prefix: str) -> str:
            parts = []
            if vend_int:
                k = f"{alias_prefix}_int"
                params[k] = tuple(vend_int)
                parts.append(f"{col}::int IN %({k})s")
            if vend_str:
                k = f"{alias_prefix}_str"
                params[k] = tuple(vend_str)
                parts.append(f"{col}::text IN %({k})s")
            return f"({' OR '.join(parts)})" if parts else "FALSE"

        if has_vendedor:
            ped_vend_cte        = vend_clause("p.pedi_vend", "pv")
            orc_vend_cte        = vend_clause("o.orca_vend", "ov")
            ped_vend_antes_cte  = vend_clause("p.pedi_vend", "pva")
            orc_vend_antes_cte  = vend_clause("o.orca_vend", "ova")

            ped_vend_col = f"""
                MAX({PED_DATA}) FILTER (
                    WHERE {ped_vend_antes_cte}
                    AND {PED_DATA} < %(data_inicial)s
                )                               AS ultimo_pedido_antes_vend,
                BOOL_OR({ped_vend_cte})         AS tem_pedido_vend,
            """
            orc_vend_col = f"""
                MAX({ORC_DATA}) FILTER (
                    WHERE {orc_vend_antes_cte}
                    AND {ORC_DATA} < %(data_inicial)s
                )                               AS ultimo_orcamento_antes_vend,
                BOOL_OR({orc_vend_cte})         AS tem_orcamento_vend,
            """
        else:
            ped_vend_col = "NULL::date AS ultimo_pedido_antes_vend,  FALSE AS tem_pedido_vend,"
            orc_vend_col = "NULL::date AS ultimo_orcamento_antes_vend, FALSE AS tem_orcamento_vend,"

        # ---------- filtro de vendedor na entidade (JOIN final) --------------

        ent_vend_filter = ""
        if has_vendedor:
            ev_parts = []
            if vend_int:
                params["ev_int"] = tuple(vend_int)
                ev_parts.append("e.enti_vend::int IN %(ev_int)s")
            if vend_str:
                params["ev_str"] = tuple(vend_str)
                ev_parts.append("e.enti_vend::text IN %(ev_str)s")

            ent_vend_cond = " OR ".join(ev_parts)
            ent_vend_filter = f"""
                AND (
                    ({ent_vend_cond})
                    OR COALESCE(pa.tem_pedido_vend,    FALSE) = TRUE
                    OR COALESCE(oa.tem_orcamento_vend, FALSE) = TRUE
                )
            """

        # ---------- filtro de entidade (nome / empresa) ----------------------

        ent_where_parts = ["1=1"]
        if empresa:
            params["ent_empr"] = empresa
            ent_where_parts.append("e.enti_empr = %(ent_empr)s")
        if cliente_nome:
            params["cliente_nome"] = f"%{cliente_nome}%"
            ent_where_parts.append("e.enti_nome ILIKE %(cliente_nome)s")

        ent_where = " AND ".join(ent_where_parts)

        # ---------- SQL ------------------------------------------------------

        sql = f"""
        WITH pedidos_agg AS (
            SELECT
                p.pedi_clie::text                                           AS clie,
                MAX({PED_DATA})                                             AS ultimo_pedido,
                MAX({PED_DATA}) FILTER (
                    WHERE {PED_DATA} < %(data_inicial)s
                )                                                           AS ultimo_pedido_antes,
                {ped_vend_col}
                BOOL_OR(
                    {PED_DATA} >= %(data_inicial)s
                    AND {PED_DATA} <= %(data_final)s
                )                                                           AS tem_pedido_periodo
            FROM pedidospisos p
            WHERE {ped_where}
            AND p.pedi_clie IS NOT NULL
            GROUP BY p.pedi_clie
        ),
        orcamentos_agg AS (
            SELECT
                o.orca_clie::text                                           AS clie,
                MAX({ORC_DATA})                                             AS ultimo_orcamento,
                MAX({ORC_DATA}) FILTER (
                    WHERE {ORC_DATA} < %(data_inicial)s
                )                                                           AS ultimo_orcamento_antes,
                {orc_vend_col}
                BOOL_OR(
                    {ORC_DATA} >= %(data_inicial)s
                    AND {ORC_DATA} <= %(data_final)s
                )                                                           AS tem_orcamento_periodo
            
            FROM orcamentopisos o
            WHERE {orc_where}
            AND o.orca_clie IS NOT NULL
            GROUP BY o.orca_clie
        )
        SELECT
            e.enti_clie,
            e.enti_nome,
            e.enti_empr,
            e.enti_fili,
            e.enti_vend,
            e.enti_tipo_enti,
            pa.ultimo_pedido,
            oa.ultimo_orcamento,
            pa.ultimo_pedido_antes,
            oa.ultimo_orcamento_antes,
            pa.ultimo_pedido_antes_vend,
            oa.ultimo_orcamento_antes_vend,
            COALESCE(pa.tem_pedido_periodo,    FALSE) AS tem_pedido_periodo,
            COALESCE(oa.tem_orcamento_periodo, FALSE) AS tem_orcamento_periodo
        FROM entidades e
        LEFT JOIN pedidos_agg   pa ON pa.clie = e.enti_clie::text
        LEFT JOIN orcamentos_agg oa ON oa.clie = e.enti_clie::text
        WHERE
            {ent_where}
            AND (pa.clie IS NOT NULL OR oa.clie IS NOT NULL)
            AND COALESCE(pa.tem_pedido_periodo,    FALSE) = FALSE
            AND COALESCE(oa.tem_orcamento_periodo, FALSE) = FALSE
            {ent_vend_filter}
        ORDER BY
            GREATEST(pa.ultimo_pedido_antes, oa.ultimo_orcamento_antes) DESC NULLS LAST
        """

        conn = connections[self.banco]
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            cols = [c.name for c in cursor.description]
            rows = cursor.fetchall()

        return [
            ClienteSemMovimentoRow(**dict(zip(cols, row)))
            for row in rows
        ]

    # ------------------------------------------------------------------
    # helpers SQL
    # ------------------------------------------------------------------

    @staticmethod
    def _where_ped(empresa, filial, params, prefix):
        parts = ["1=1"]
        if empresa:
            params[f"{prefix}_empr"] = empresa
            parts.append(f"p.pedi_empr = %({prefix}_empr)s")
        if filial:
            params[f"{prefix}_fili"] = filial
            parts.append(f"p.pedi_fili = %({prefix}_fili)s")
        return " AND ".join(parts)

    @staticmethod
    def _where_orc(empresa, filial, params, prefix):
        parts = ["1=1"]
        if empresa:
            params[f"{prefix}_empr"] = empresa
            parts.append(f"o.orca_empr = %({prefix}_empr)s")
        if filial:
            params[f"{prefix}_fili"] = filial
            parts.append(f"o.orca_fili = %({prefix}_fili)s")
        return " AND ".join(parts)

    @staticmethod
    def _vend_clause(col, vend_int, vend_str, params, prefix):
        parts = []
        if vend_int:
            key = f"{prefix}_int"
            params[key] = tuple(vend_int)
            parts.append(f"p.{col}::int IN %({key})s" if "pedi" in col else f"o.{col}::int IN %({key})s")
        if vend_str:
            key = f"{prefix}_str"
            params[key] = tuple(vend_str)
            parts.append(f"p.{col}::text IN %({key})s" if "pedi" in col else f"o.{col}::text IN %({key})s")
        return " OR ".join(parts) if parts else "FALSE"

    @staticmethod
    def _placeholders(values, params, prefix):
        if not values:
            return ""
        keys = []
        for i, v in enumerate(values):
            k = f"{prefix}_{i}"
            params[k] = v
            keys.append(f"%({k})s")
        return ", ".join(keys)