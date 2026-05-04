
# ── orcamento_impressao_service.py ──────────────────────────────────────────
 
import base64
from functools import lru_cache
from pathlib import Path
from decimal import Decimal
from itertools import groupby, zip_longest
 
from Entidades.models import Entidades
from Pisos.models import Itensorcapisos
from django.utils import timezone
 
 
class OrcamentoPisosImpressaoService:
    @staticmethod
    @lru_cache(maxsize=4)
    def _carregar_logo_b64(nome_arquivo: str) -> str:
        try:
            base_dir = Path(__file__).resolve().parents[2]
            path = base_dir / "staticfiles" / nome_arquivo
            data = path.read_bytes()
            return base64.b64encode(data).decode("utf-8")
        except Exception:
            return ""

    @staticmethod
    def obter_contexto(*, banco: str, orcamento) -> dict:
        cliente = (
            Entidades.objects.using(banco)
            .filter(enti_clie=orcamento.orca_clie)
            .first()
        )
        vendedor = (
            Entidades.objects.using(banco)
            .filter(enti_clie=orcamento.orca_vend)
            .first()
        )
 
        itens = list(
            Itensorcapisos.objects.using(banco)
            .filter(
                item_empr=orcamento.orca_empr,
                item_fili=orcamento.orca_fili,
                item_orca=orcamento.orca_nume,
            )
            .order_by("item_ambi", "item_nume")
        )
 
        OrcamentoPisosImpressaoService._enriquecer_itens_com_produtos(banco=banco, itens=itens)

        financeiro = OrcamentoPisosImpressaoService._obter_financeiro(
            banco=banco, orcamento=orcamento
        )
 
        grupos = OrcamentoPisosImpressaoService._agrupar_itens_por_ambiente(itens)
        total_ambientes = OrcamentoPisosImpressaoService._calcular_totais_por_ambiente(itens)
        subtotal = OrcamentoPisosImpressaoService._calcular_subtotal(orcamento)
        data_hoje_extenso = OrcamentoPisosImpressaoService._formatar_data_hoje_extenso()
        financeiro_linhas = [{"seq": i + 1, "obj": f} for i, f in enumerate(financeiro)]
        financeiro_colunas = list(zip_longest(financeiro_linhas[::2], financeiro_linhas[1::2]))
        logo_orcamento_b64 = OrcamentoPisosImpressaoService._carregar_logo_b64("logopgorcamentos.png")
 
        return {
            "cliente": cliente,
            "vendedor": vendedor,
            "itens": itens,
            "grupos": grupos,
            "financeiro": financeiro,
            "financeiro_colunas": financeiro_colunas,
            "total_ambientes": total_ambientes,
            "subtotal": subtotal,
            "data_hoje_extenso": data_hoje_extenso,
            "logo_orcamento_b64": logo_orcamento_b64,
        }
 
    @staticmethod
    def _obter_financeiro(*, banco: str, orcamento):
        """
        Busca os títulos/parcelas do orçamento.
        Ajuste o model/filtro conforme seu schema real.
        """
        try:
            from Financeiro.models import Titulos  # ajuste o import real
 
            return list(
                Titulos.objects.using(banco)
                .filter(
                    fina_empr=orcamento.orca_empr,
                    fina_fili=orcamento.orca_fili,
                    fina_orca=orcamento.orca_nume,
                )
                .order_by("fina_venc")
            )
        except Exception:
            return []
 
    @staticmethod
    def _calcular_totais_por_ambiente(itens) -> dict:
        totais = {}
        for item in itens:
            chave = getattr(item, "item_nome_ambi", None) or getattr(item, "item_ambi", "") or ""
            valor = Decimal(str(getattr(item, "item_suto", 0) or 0))
            totais[chave] = totais.get(chave, Decimal("0")) + valor
        return totais

    @staticmethod
    def _agrupar_itens_por_ambiente(itens):
        def _chave_ambiente(item):
            valor = getattr(item, "item_nome_ambi", None) or getattr(item, "item_ambi", "") or ""
            if isinstance(valor, str):
                return valor.strip()
            return valor

        itens_ordenados = sorted(itens, key=_chave_ambiente)
        grupos = []
        for nome_ambiente, itens_iter in groupby(itens_ordenados, key=_chave_ambiente):
            itens_grupo = list(itens_iter)
            total = Decimal("0")
            for item in itens_grupo:
                total += Decimal(str(getattr(item, "item_suto", 0) or 0))
            grupos.append({"nome": nome_ambiente, "itens": itens_grupo, "total": total})
        return grupos

    @staticmethod
    def _enriquecer_itens_com_produtos(*, banco: str, itens) -> None:
        try:
            from Produtos.models import Produtos
        except Exception:
            return

        codigos = {getattr(i, "item_prod", None) for i in itens}
        codigos.discard(None)
        if not codigos:
            return

        produtos = (
            Produtos.objects.using(banco)
            .filter(prod_codi__in=list(codigos))
            .select_related("prod_marc", "prod_unme")
        )
        mapa = {p.prod_codi: p for p in produtos}

        for item in itens:
            prod = mapa.get(getattr(item, "item_prod", None))
            caixas = getattr(item, "item_caix", None)
            setattr(item, "item_caixas", caixas if caixas is not None else 0)
            if not prod:
                setattr(item, "item_marc", "")
                setattr(item, "item_unid", "")
                continue
            marca = getattr(getattr(prod, "prod_marc", None), "nome", "") or ""
            unid = getattr(getattr(prod, "prod_unme", None), "unid_codi", "") or ""
            setattr(item, "item_marc", marca)
            setattr(item, "item_unid", unid)

    @staticmethod
    def _calcular_subtotal(orcamento) -> Decimal:
        total = Decimal(str(getattr(orcamento, "orca_tota", 0) or 0))
        desconto = Decimal(str(getattr(orcamento, "orca_desc", 0) or 0))
        credito = Decimal(str(getattr(orcamento, "orca_cred", 0) or 0))
        frete = Decimal(str(getattr(orcamento, "orca_fret", 0) or 0))
        return total + desconto + credito - frete

    @staticmethod
    def _formatar_data_hoje_extenso() -> str:
        try:
            hoje = timezone.localdate()
        except Exception:
            hoje = timezone.now().date()
        meses = [
            "",
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]
        mes = meses[hoje.month]
        return f"Ponta Grossa , {hoje.day} de {mes} de {hoje.year}."
