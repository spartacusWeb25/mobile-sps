"""
Pisos/services/pedido_emitir_nfe_service.py

Emissão (total ou parcial) de NF-e a partir de um PedidoPisos.

Fluxo:
  1. Valida as quantidades solicitadas contra o saldo ainda não emitido.
  2. Monta os itens rateados (somente as quantidades pedidas).
  3. Chama EmissaoNotaService — que cria a nota, calcula impostos do zero
     com os itens parciais e envia para SEFAZ.
  4. Após autorização, registra a quantidade emitida em cada item
     (campo iped_quan_emit) e, se o pedido ficar totalmente emitido,
     marca pedi_stat_nfe = 'E'; caso contrário, 'P' (pendente).

Modelos assumidos
─────────────────
  Itenspedidospisos:
    iped_quan      – quantidade total do item
    iped_quan_emit – quantidade já emitida (default 0)   # TODO: adicionar campo se não existir
    iped_unit      – valor unitário
    iped_desc      – desconto unitário
    iped_prod      – FK / id do produto
    iped_empr / iped_fili / iped_pedi / iped_nume

  Pedidospisos:
    pedi_stat_nfe  – 'N' = não emitido | 'P' = parcial | 'E' = totalmente emitido
                     # TODO: adicionar campo se não existir
    pedi_form_rece – código da forma de pagamento
    pedi_tipo_oper – tipo de operação (para derivar CFOP)
"""

import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from Pisos.models import Pedidospisos, Itenspedidospisos
from Pisos.services.utils_service import parse_decimal
from Notas_Fiscais.emissao.emissao_nota_service import EmissaoNotaService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes / helpers
# ---------------------------------------------------------------------------

MAPA_TPAG = {
    "54": "01",  # Dinheiro
    "50": "02",  # Cheque pré
    "01": "02",  # Cheque
    "51": "03",  # Cartão de Crédito
    "52": "04",  # Cartão de Débito
    "55": "16",  # Depósito em conta
    "53": "15",  # Boleto bancário
    "60": "17",  # PIX
    "56": "01",  # Venda à vista
}

MAPA_CFOP = {
    "DEVOLUCAO_VENDA": "1202",
    "BONIFICACAO": "5910",
    "REMESSA": "5915",
    "TRANSFERENCIA": "5152",
}
CFOP_PADRAO = "5102"


def _cfop_para_tipo(tipo_oper: str) -> str:
    return MAPA_CFOP.get(tipo_oper, CFOP_PADRAO)


def _quantidade_emitida(item) -> Decimal:
    """Retorna quanto já foi emitido no item, com fallback seguro."""
    return parse_decimal(getattr(item, "iped_quan_emit", None) or 0)


def _saldo_disponivel(item) -> Decimal:
    total = parse_decimal(item.iped_quan or 0)
    emitido = _quantidade_emitida(item)
    return max(total - emitido, Decimal("0"))


# ---------------------------------------------------------------------------
# DTO interno
# ---------------------------------------------------------------------------

class ItemEmissaoDTO:
    """Representa um item a ser emitido com quantidade parcial."""

    def __init__(self, item_obj: Itenspedidospisos, quantidade: Decimal):
        self.item_obj = item_obj
        self.quantidade = quantidade


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------

class PedidoEmitirNFeService:
    """
    Parâmetros
    ──────────
    banco        : alias do banco (multi-tenant)
    pedido       : instância de Pedidospisos
    itens_emitir : lista de dicts [ {"item_nume": int, "quantidade": float/Decimal}, ... ]
                   Se None ou vazio → emite todos os itens com saldo disponível (emissão total).
    empresa      : int (pedi_empr)
    filial       : int (pedi_fili)
    """

    def __init__(self, *, banco: str, pedido: Pedidospisos, empresa: int, filial: int):
        self.banco = banco
        self.pedido = pedido
        self.empresa = empresa
        self.filial = filial

    # ------------------------------------------------------------------
    # Ponto de entrada
    # ------------------------------------------------------------------

    @transaction.atomic
    def emitir(self, itens_emitir: list[dict] | None = None) -> dict:
        """
        itens_emitir = [{"item_nume": 1, "quantidade": 5}, ...]
        Retorna o dict de resultado de EmissaoNotaService.emitir_nota.
        """
        itens_db = self._carregar_itens()

        dtos = self._resolver_quantidades(itens_db, itens_emitir)

        if not dtos:
            raise ValidationError("Nenhum item com saldo disponível para emissão.")

        nota_data = self._montar_nota_data(dtos)

        resultado = EmissaoNotaService.emitir_nota(
            dto_dict=nota_data,
            empresa=self.empresa,
            filial=self.filial,
            database=self.banco,
        )

        sefaz = resultado.get("sefaz", {})
        if str(sefaz.get("status")) in ("100", "204"):
            self._registrar_emissao(dtos)

        return resultado

    def listar_itens_nfe(self) -> dict:
        itens_db = self._carregar_itens()
        itens = []
        total = Decimal("0")

        for item in itens_db.values():
            saldo = _saldo_disponivel(item)
            emitido = _quantidade_emitida(item)
            produto_nome = getattr(item, "item_prod_nome", "") or getattr(getattr(item, "produto", None), "prod_nome", "") or ""
            unitario = parse_decimal(getattr(item, "item_unit", 0))
            subtotal = saldo * unitario
            total += subtotal
            itens.append({
                "item_nume": item.iped_nume,
                "ambiente": getattr(item, "item_nome_ambi", None) or getattr(item, "item_ambi", None) or "",
                "produto_codigo": item.iped_prod,
                "produto_nome": produto_nome,
                "quantidade_total": str(parse_decimal(getattr(item, "iped_quan", 0))),
                "quantidade_emitida": str(emitido),
                "saldo": str(saldo),
                "unitario": str(unitario),
                "subtotal": str(subtotal),
            })

        return {
            "pedido_nume": int(self.pedido.pedi_nume),
            "cliente_nome": getattr(getattr(self.pedido, "cliente", None), "enti_nome", None) or "",
            "status_nfe": str(getattr(self.pedido, "pedi_stat_nfe", "N") or "N"),
            "total": str(total),
            "itens": itens,
        }

    # ------------------------------------------------------------------
    # Carrega itens do pedido
    # ------------------------------------------------------------------

    def _carregar_itens(self) -> dict[int, Itenspedidospisos]:
        qs = Itenspedidospisos.objects.using(self.banco).filter(
            iped_empr=self.empresa,
            iped_fili=self.filial,
            iped_pedi=self.pedido.pedi_nume,
        ).select_related("produto")

        return {item.iped_nume: item for item in qs}

    # ------------------------------------------------------------------
    # Resolve quais quantidades emitir
    # ------------------------------------------------------------------

    def _resolver_quantidades(
        self,
        itens_db: dict[int, Itenspedidospisos],
        itens_emitir: list[dict] | None,
    ) -> list[ItemEmissaoDTO]:
        """
        Se itens_emitir for fornecido → valida e usa as quantidades informadas.
        Se None → usa o saldo completo de cada item (emissão total do pendente).
        """
        dtos: list[ItemEmissaoDTO] = []

        if itens_emitir:
            for entry in itens_emitir:
                item_nume = int(entry["item_nume"])
                qtd_solicitada = parse_decimal(entry["quantidade"])

                item = itens_db.get(item_nume)
                if not item:
                    raise ValidationError(
                        f"Item {item_nume} não encontrado no pedido {self.pedido.pedi_nume}."
                    )

                saldo = _saldo_disponivel(item)
                if qtd_solicitada <= 0:
                    raise ValidationError(f"Quantidade inválida para o item {item_nume}.")
                if qtd_solicitada > saldo:
                    raise ValidationError(
                        f"Item {item_nume}: quantidade solicitada ({qtd_solicitada}) "
                        f"excede saldo disponível ({saldo})."
                    )

                dtos.append(ItemEmissaoDTO(item, qtd_solicitada))

        else:
            # Emissão total — todos os itens com saldo
            for item in itens_db.values():
                saldo = _saldo_disponivel(item)
                if saldo > 0:
                    dtos.append(ItemEmissaoDTO(item, saldo))

        return dtos

    # ------------------------------------------------------------------
    # Monta o dict que vai para EmissaoNotaService
    # ------------------------------------------------------------------

    def _montar_nota_data(self, dtos: list[ItemEmissaoDTO]) -> dict:
        pedido = self.pedido
        cliente = pedido.cliente
        if not cliente:
            raise ValidationError("Cliente não encontrado no pedido.")

        cfop = _cfop_para_tipo(str(pedido.pedi_tipo_oper or ""))
        tpag = MAPA_TPAG.get(str(pedido.pedi_form_rece or "54"), "01")

        itens = []
        for dto in dtos:
            item = dto.item_obj
            prod = item.produto
            if not prod:
                raise ValidationError(
                    f"Produto do item {item.iped_nume} não encontrado."
                )

            try:
                prod_id = int(item.iped_prod)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"Produto inválido no item {item.iped_nume}: {item.iped_prod}"
                )

            itens.append({
                "produto": prod_id,
                "quantidade": float(dto.quantidade),
                "unitario": float(parse_decimal(item.iped_unit or 0)),
                "desconto": float(parse_decimal(item.iped_desc or 0)),
                "cfop": cfop,
                "ncm": prod.prod_ncm,
                "cest": None,
                "cst_icms": "000",
                "cst_pis": "01",
                "cst_cofins": "01",
            })

        return {
            "modelo": "55",
            "serie": "1",
            "numero": 0,
            "data_emissao": str(pedido.pedi_data),
            "data_saida": None,
            "tipo_operacao": 1,
            "finalidade": 1,
            "ambiente": 2,
            "destinatario": cliente.enti_clie,
            "itens": itens,
            "tpag": tpag,
        }

    # ------------------------------------------------------------------
    # Registra o que foi emitido e atualiza status do pedido
    # ------------------------------------------------------------------

    def _registrar_emissao(self, dtos: list[ItemEmissaoDTO]) -> None:
        """
        Incrementa iped_quan_emit em cada item emitido e
        recalcula pedi_stat_nfe no pedido.
        """
        for dto in dtos:
            item = dto.item_obj
            atual = _quantidade_emitida(item)
            nova = atual + dto.quantidade

            # TODO: garantir que iped_quan_emit existe no model e migration
            Itenspedidospisos.objects.using(self.banco).filter(
                iped_empr=item.iped_empr,
                iped_fili=item.iped_fili,
                iped_pedi=item.iped_pedi,
                iped_nume=item.iped_nume,
            ).update(iped_quan_emit=nova)

        self._atualizar_status_pedido()

    def _atualizar_status_pedido(self) -> None:
        """
        Verifica se todos os itens estão totalmente emitidos.
        pedi_stat_nfe: 'N' → 'P' (parcial) ou 'E' (totalmente emitido)
        """
        itens = Itenspedidospisos.objects.using(self.banco).filter(
            iped_empr=self.empresa,
            iped_fili=self.filial,
            iped_pedi=self.pedido.pedi_nume,
        )

        totalmente_emitido = all(
            _saldo_disponivel(i) == 0 for i in itens
        )

        # TODO: garantir que pedi_stat_nfe existe no model e migration
        novo_status = "E" if totalmente_emitido else "P"
        Pedidospisos.objects.using(self.banco).filter(
            pedi_empr=self.empresa,
            pedi_fili=self.filial,
            pedi_nume=self.pedido.pedi_nume,
        ).update(pedi_stat_nfe=novo_status)

        logger.info(
            "Pedido %s — status NF-e atualizado para '%s'",
            self.pedido.pedi_nume,
            novo_status,
        )
