# ── pedido_impressao_service.py ─────────────────────────────────────────────
 
import base64
from functools import lru_cache
from pathlib import Path
from decimal import Decimal
from itertools import groupby, zip_longest
 
from Entidades.models import Entidades
from Pisos.models import Itenspedidospisos
from django.utils import timezone
 
 
class PedidoPisosImpressaoService:
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
    def obter_contexto(*, banco: str, pedido) -> dict:
        cliente = (
            Entidades.objects.using(banco)
            .filter(enti_clie=pedido.pedi_clie)
            .first()
        )
        vendedor = (
            Entidades.objects.using(banco)
            .filter(enti_clie=pedido.pedi_vend)
            .first()
        )
 
        itens = list(
            Itenspedidospisos.objects.using(banco)
            .filter(
                item_empr=pedido.pedi_empr,
                item_fili=pedido.pedi_fili,
                item_pedi=pedido.pedi_nume,
            )
            .order_by("item_ambi", "item_nume")
        )
 
        PedidoPisosImpressaoService._enriquecer_itens_com_produtos(banco=banco, itens=itens)

        financeiro = PedidoPisosImpressaoService._obter_financeiro(
            banco=banco, pedido=pedido
        )
 
        grupos = PedidoPisosImpressaoService._agrupar_itens_por_ambiente(itens)
        total_ambientes = PedidoPisosImpressaoService._calcular_totais_por_ambiente(itens)
        subtotal = PedidoPisosImpressaoService._calcular_subtotal(pedido)
        data_hoje_extenso = PedidoPisosImpressaoService._formatar_data_hoje_extenso()
        financeiro_linhas = [{"seq": i + 1, "obj": f} for i, f in enumerate(financeiro)]
        financeiro_colunas = list(zip_longest(financeiro_linhas[::2], financeiro_linhas[1::2]))
        logo_pedido_b64 = PedidoPisosImpressaoService._carregar_logo_b64("logopgpisos.png")
 
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
            "logo_pedido_b64": logo_pedido_b64,
        }
 
    @staticmethod
    def _obter_financeiro(*, banco: str, pedido):
        """
        Busca os títulos financeiros vinculados ao pedido.
        Ajuste o model/filtro conforme seu schema real.
        """
        try:
            from Financeiro.models import Titulos  # ajuste o import real
 
            return list(
                Titulos.objects.using(banco)
                .filter(
                    fina_empr=pedido.pedi_empr,
                    fina_fili=pedido.pedi_fili,
                    fina_pedi=pedido.pedi_nume,
                )
                .order_by("fina_venc")
            )
        except Exception:
            return []
 
    @staticmethod
    def _calcular_totais_por_ambiente(itens) -> dict:
        """
        Retorna { nome_ambiente: total_decimal } para uso no template.
        """
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
    def _calcular_subtotal(pedido) -> Decimal:
        total = Decimal(str(getattr(pedido, "pedi_tota", 0) or 0))
        desconto = Decimal(str(getattr(pedido, "pedi_desc", 0) or 0))
        credito = Decimal(str(getattr(pedido, "pedi_cred", 0) or 0))
        frete = Decimal(str(getattr(pedido, "pedi_fret", 0) or 0))
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
