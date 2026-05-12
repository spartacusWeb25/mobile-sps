# controledevisitas/services/gerar_orcamento_pisos_service.py

from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from controledevisitas.models import Controlevisita, ItensVisita
from Pisos.models import Orcamentopisos,Itensorcapisos
from Pisos.services.metragem_service import MetragemProdutoService
from Pisos.services.preco_service import get_preco_produto
from Pisos.services.utils_service import parse_decimal, arredondar
from controledevisitas.service.etapa_orcamento_gerado_service import EtapaOrcamentoGeradoService


class GerarOrcamentoPisosDaVisitaService:
    """
    Gera um orçamento de Pisos a partir de uma visita comercial.

    Fluxo:
    - Busca a visita
    - Busca os itens da visita
    - Cria cabeçalho do orçamento
    - Recalcula os itens usando o service de Pisos
    - Cria os itens do orçamento
    - Atualiza o total do orçamento
    - Marca a visita como proposta gerada
    """

    def __init__(self, *, banco: str, empresa_id: int, filial_id: int, usuario=None):
        self.banco = banco
        self.empresa_id = int(empresa_id)
        self.filial_id = int(filial_id)
        self.usuario = usuario

    @transaction.atomic
    def executar(self, *, ctrl_id: int, condicao: str = "0"):
        visita = self.buscar_visita(ctrl_id)
        itens_visita = self.buscar_itens_visita(visita)

        if not itens_visita:
            raise ValueError("A visita não possui itens para gerar orçamento.")

        orcamento = self.criar_cabecalho(visita)

        total_geral = Decimal("0.00")

        for sequencia, item_visita in enumerate(itens_visita, start=1):
            item_orcamento, total_item = self.criar_item_orcamento(
                orcamento=orcamento,
                item_visita=item_visita,
                sequencia=sequencia,
                condicao=condicao,
            )

            total_geral += parse_decimal(total_item)

        self.atualizar_total_orcamento(
            orcamento=orcamento,
            total=total_geral,
        )

        self.marcar_visita_com_orcamento(
            visita=visita,
            orcamento=orcamento,
        )

        return orcamento

    def buscar_visita(self, ctrl_id: int):
        return (
            Controlevisita.objects
            .using(self.banco)
            .select_related("ctrl_empresa", "ctrl_cliente", "ctrl_vendedor")
            .get(
                ctrl_id=ctrl_id,
                ctrl_empresa_id=self.empresa_id,
                ctrl_filial=self.filial_id,
            )
        )

    def buscar_itens_visita(self, visita):
        return list(
            ItensVisita.objects
            .using(self.banco)
            .filter(item_visita=visita)
            .order_by("item_id")
        )

    def proximo_numero_orcamento(self):
        ultimo = (
            Orcamentopisos.objects
            .using(self.banco)
            .filter(
                orca_empr=self.empresa_id,
                orca_fili=self.filial_id,
            )
            .aggregate(maior=Max("orca_nume"))
            .get("maior")
            or 0
        )

        return int(ultimo) + 1
    
    def data_hoje(self):
        now = timezone.now()
        if timezone.is_naive(now):
            return now.date()
        return timezone.localtime(now).date()

    def criar_cabecalho(self, visita):
        numero = self.proximo_numero_orcamento()

        cliente_id = getattr(
            getattr(visita, "ctrl_cliente", None),
            "enti_clie",
            None,
        )

        vendedor_id = getattr(
            getattr(visita, "ctrl_vendedor", None),
            "enti_clie",
            None,
        )

        observacao = self.montar_observacao(visita)

        orcamento = Orcamentopisos.objects.using(self.banco).create(
            orca_empr=self.empresa_id,
            orca_fili=self.filial_id,
            orca_nume=numero,

            # Cliente / vendedor
            orca_clie=cliente_id,
            orca_vend=vendedor_id,

            # Datas
            orca_data=self.data_hoje(),

            # Totais
            orca_tota=Decimal("0.00"),

            # Observação
            orca_obse=observacao,
        )

        return orcamento

    def criar_item_orcamento(self, *, orcamento, item_visita, sequencia: int, condicao: str):
        produto_id = getattr(item_visita, "item_prod", None)

        if not produto_id:
            raise ValueError("Item da visita sem produto informado.")

        metragem = parse_decimal(getattr(item_visita, "item_m2", None) or 0)
        quantidade = parse_decimal(getattr(item_visita, "item_quan", None) or 0)

        if metragem <= 0:
            raise ValueError(f"Item {sequencia} está sem metragem/quantidade válida.")

        percentual_quebra = parse_decimal(
            getattr(item_visita, "item_queb", 0)
            or getattr(item_visita, "percentual_quebra", 0)
            or 0
        )

        try:
            preco_unitario = get_preco_produto(
                self.banco,
                produto_id,
                condicao,
                empresa=self.empresa_id,
                filial=self.filial_id,
            )
        except Exception:
            calculo = MetragemProdutoService().executar(
                banco=self.banco,
                produto_id=produto_id,
                tamanho_m2=metragem,
                percentual_quebra=percentual_quebra,
                condicao=condicao,
                empresa_id=self.empresa_id,
                filial_id=self.filial_id,
            )
            preco_unitario = parse_decimal(calculo["preco_unitario"])

        caixas_necessarias = getattr(item_visita, "item_caix", None)
        if quantidade <= 0:
            calculo = MetragemProdutoService().executar(
                banco=self.banco,
                produto_id=produto_id,
                tamanho_m2=metragem,
                percentual_quebra=percentual_quebra,
                condicao=condicao,
                empresa_id=self.empresa_id,
                filial_id=self.filial_id,
            )
            quantidade = parse_decimal(calculo["metragem_real"])
            caixas_necessarias = calculo.get("caixas_necessarias")

        total_item = arredondar(quantidade * parse_decimal(preco_unitario))

        item = Itensorcapisos.objects.using(self.banco).create(
            item_empr=self.empresa_id,
            item_fili=self.filial_id,

            # vínculo com orçamento
            item_orca=orcamento.orca_nume,
            item_nume=sequencia,
            item_prod=produto_id,

            # quantidade digitada / metragem solicitada
            item_m2=metragem,

            # percentual de perda/quebra

            # percentual de perda/quebra
            item_queb=percentual_quebra,

            item_quan=quantidade,

            # preço e subtotal
            item_unit=preco_unitario,
            item_suto=total_item,

            # ambiente, se vier da visita
            item_ambi=getattr(item_visita, "item_ambi", None) or 1,
            item_nome_ambi=getattr(item_visita, "item_nome_ambi", None),
            item_caix=caixas_necessarias,

            # observação
            item_obse=getattr(item_visita, "item_obse", None),
        )

        return item, total_item

    def atualizar_total_orcamento(self, *, orcamento, total):
        orcamento.orca_tota = arredondar(total)
        orcamento.save(using=self.banco, update_fields=["orca_tota"])

    def marcar_visita_com_orcamento(self, *, visita, orcamento):
        etapa = EtapaOrcamentoGeradoService(
            banco=self.banco,
            empresa_id=self.empresa_id,
        ).executar()
        visita.ctrl_prop = 1
        visita.ctrl_proj = str(orcamento.orca_nume)
        visita.ctrl_etapa = etapa
        visita.save(
            using=self.banco,
            update_fields=["ctrl_prop", "ctrl_proj", "ctrl_etapa"],
        )

    def montar_observacao(self, visita):
        partes = [
            f"Orçamento gerado automaticamente pela visita #{visita.ctrl_id}.",
        ]

        if getattr(visita, "ctrl_contato", None):
            partes.append(f"Contato: {visita.ctrl_contato}")

        if getattr(visita, "ctrl_fone", None):
            partes.append(f"Telefone: {visita.ctrl_fone}")

        if getattr(visita, "ctrl_obse", None):
            partes.append(f"Observação da visita: {visita.ctrl_obse}")

        return "\n".join(partes)
