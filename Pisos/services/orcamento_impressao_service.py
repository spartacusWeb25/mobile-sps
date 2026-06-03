
# ── orcamento_impressao_service.py ──────────────────────────────────────────
 
import base64
from functools import lru_cache
from pathlib import Path
from decimal import Decimal
from itertools import groupby, zip_longest
 
from Entidades.models import Entidades
from Licencas.models import Filiais
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
    @lru_cache(maxsize=32)
    def _carregar_logo_filial_b64(*, banco: str, empresa_id: int, filial_id: int) -> str:
        try:
            filial = (
                Filiais.objects.using(banco)
                .filter(empr_empr=empresa_id, empr_codi=filial_id)
                .first()
            )
            if not filial:
                return ""
            raw = getattr(filial, "empr_logo", None)
            if not raw:
                raw = getattr(filial, "empr_logo_2", None)
            if not raw:
                return ""
            if isinstance(raw, memoryview):
                raw = raw.tobytes()
            if isinstance(raw, bytes):
                return base64.b64encode(raw).decode("utf-8")
            return base64.b64encode(bytes(raw)).decode("utf-8")
        except Exception:
            return ""

    @staticmethod
    def _intro_por_filial(filial_id) -> str:
        try:
            filial_id = int(filial_id)
        except Exception:
            filial_id = None

        if filial_id == 4:
            return (
                "Agradecemos a oportunidade de apresentar esta proposta e parabenizamos sua escolha em conhecer as soluções Kohler.<br><br>"
                "Com mais de 150 anos de tradição, a Kohler é uma referência mundial em design, inovação e qualidade, desenvolvendo produtos que aliam sofisticação, tecnologia e desempenho. Presente nos mais exigentes projetos residenciais e corporativos, a marca é reconhecida por criar ambientes que agregam valor, conforto e elegância."
            )

        return (
            "Estamos muito felizes pela oportunidade de apresentar essa proposta a você!<br>"
            "A PG PISOS é especializada em pisos, materiais de acabamento, louças, metais e<br>"
            "portas e janelas termoacústicas. Desde 2007 em Ponta Grossa, contamos com<br>"
            "equipe própria e especializada, garantindo qualidade com as melhores marcas do<br>"
            "mercado nacional e internacional."
        )

    @staticmethod
    def obter_contexto(*, banco: str, orcamento) -> dict:
        filial = (
            Filiais.objects.using(banco)
            .filter(empr_empr=orcamento.orca_empr, empr_codi=orcamento.orca_fili)
            .first()
        )
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
        logo_orcamento_b64 = OrcamentoPisosImpressaoService._carregar_logo_filial_b64(
            banco=banco, empresa_id=orcamento.orca_empr, filial_id=orcamento.orca_fili
        ) or OrcamentoPisosImpressaoService._carregar_logo_b64("logopgorcamentos.png")
 
        return {
            "filial": filial,
            "ocultar_kg_caixas": bool(getattr(filial, "empr_codi", None) == 4),
            "intro_html": OrcamentoPisosImpressaoService._intro_por_filial(getattr(filial, "empr_codi", None)),
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
            kg_total = getattr(item, "item_kg", None)
            if not kg_total:
                kg_total = getattr(item, "item_kg_total", None)
            if not kg_total and prod:
                kg_por_caixa = getattr(prod, "prod_cera_kgcx", None)
                if kg_por_caixa not in (None, ""):
                    try:
                        kg_total = Decimal(str(kg_por_caixa)) * Decimal(str(caixas or 0))
                    except Exception:
                        kg_total = None
            setattr(item, "item_kg_total", kg_total if kg_total is not None else Decimal("0"))
            if not prod:
                setattr(item, "item_marc", "")
                setattr(item, "item_unid", "")
                continue
            marca = getattr(getattr(prod, "prod_marc", None), "nome", "") or ""
            unid = getattr(getattr(prod, "prod_unme", None), "unid_codi", "") or ""
            setattr(item, "item_marc", marca)
            setattr(item, "item_unid", unid)
            descricao = getattr(item, "item_prod_nome", None) or getattr(prod, "prod_nome", "") or getattr(item, "item_nome", "") or ""
            setattr(item, "item_prod_nome", descricao)
            nome_item = getattr(item, "item_nome", "") or ""
            setattr(item, "item_nome", nome_item)
    
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
