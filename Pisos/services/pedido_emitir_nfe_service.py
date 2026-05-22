"""
Pisos/services/pedido_emitir_nfe_service.py

Emissão (total ou parcial) de NF-e a partir de um PedidoPisos.

Fluxo:
  1. Valida as quantidades solicitadas contra o saldo ainda não emitido.
  2. Monta os itens rateados (somente as quantidades pedidas).
  3. Chama EmissaoNotaService — que cria a nota, calcula impostos do zero
     com os itens parciais e envia para SEFAZ.
  4. Após autorização, registra a quantidade emitida em cada item
     (campo item_quan_emit) e, se o pedido ficar totalmente emitido,
     marca pedi_stat_nfe = 'E'; caso contrário, 'P' (pendente).

Modelos assumidos
─────────────────
  Itenspedidospisos:
    item_quan      – quantidade total do item
    item_quan_emit – quantidade já emitida (default 0)   # TODO: adicionar campo se não existir
    item_unit      – valor unitário
    item_desc      – desconto unitário
    item_prod      – FK / id do produto
    item_empr / item_fili / item_pedi / item_nume

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
    return parse_decimal(getattr(item, "item_quan_emit", None) or 0)


def _saldo_disponivel(item) -> Decimal:
    total = parse_decimal(item.item_quan or 0)
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
                "item_nume": item.item_nume,
                "ambiente": getattr(item, "item_nome_ambi", None) or getattr(item, "item_ambi", None) or "",
                "produto_codigo": item.item_prod,
                "produto_nome": produto_nome,
                "quantidade_total": str(parse_decimal(getattr(item, "item_quan", 0))),
                "quantidade_emitida": str(emitido),
                "saldo": str(saldo),
                "unitario": str(unitario),
                "subtotal": str(subtotal),
            })

        try:
            from Entidades.models import Entidades
            cliente_nome = Entidades.objects.using(self.banco).filter(
                enti_clie=self.pedido.pedi_clie,
                enti_empr=self.pedido.pedi_empr,
            ).values_list('enti_nome', flat=True).first()
        except Exception:
            cliente_nome = None

        if not cliente_nome:
            cliente_nome = str(self.pedido.pedi_clie) if getattr(self.pedido, 'pedi_clie', None) is not None else ""

        return {
            "pedido_nume": int(self.pedido.pedi_nume),
            "cliente_nome": cliente_nome,
            "status_nfe": str(getattr(self.pedido, "pedi_stat_nfe", "N") or "N"),
            "total": str(total),
            "itens": itens,
        }

    # ------------------------------------------------------------------
    # Carrega itens do pedido
    # ------------------------------------------------------------------

    def _carregar_itens(self) -> dict[int, Itenspedidospisos]:
        qs = Itenspedidospisos.objects.using(self.banco).filter(
            item_empr=self.empresa,
            item_fili=self.filial,
            item_pedi=self.pedido.pedi_nume,
        ).only('item_empr','item_fili','item_pedi','item_prod','item_nume','item_nome_ambi','item_quan','item_unit','item_suto','item_caix')

        items = list(qs)

        # Pré-carrega objetos Produtos correspondentes aos códigos encontrados
        codigos = {str(getattr(i, 'item_prod', '')).strip() for i in items if getattr(i, 'item_prod', None) is not None}
        empresas_itens = {str(getattr(i, 'item_empr', '')).strip() for i in items if getattr(i, 'item_empr', None) is not None}
        produtos_map = {}
        if codigos:
            try:
                from Produtos.models import Produtos
                produtos_qs = Produtos.objects.using(self.banco).filter(
                    prod_codi__in=list(codigos),
                    prod_empr__in=list(empresas_itens) if empresas_itens else list(empresas_itens),
                ).only('prod_empr', 'prod_codi', 'prod_nome')
                produtos_map = { (str(p.prod_empr), str(p.prod_codi)): p for p in produtos_qs }
            except Exception:
                produtos_map = {}

        # Anexa atributo 'produto' nos itens para compatibilidade com o restante do serviço
        for it in items:
            key = (str(getattr(it, 'item_empr', '')).strip(), str(getattr(it, 'item_prod', '')).strip())
            it.produto = produtos_map.get(key)

        return {item.item_nume: item for item in items}

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
        # Resolver cliente pelo campo pedi_clie (legacy) — Pedidospisos não tem relação direta
        cliente = None
        try:
            from Entidades.models import Entidades
            cliente = Entidades.objects.using(self.banco).filter(
                enti_clie=pedido.pedi_clie,
                enti_empr=pedido.pedi_empr,
            ).first()
        except Exception:
            cliente = None

        if not cliente:
            raise ValidationError("Cliente não encontrado no pedido.")

        tipo_oper = str(getattr(pedido, 'pedi_tipo_oper', 'VENDA') or 'VENDA')
        cfop = _cfop_para_tipo(tipo_oper)
        tpag = MAPA_TPAG.get(str(getattr(pedido, 'pedi_form_rece', '54')), "01")

        try:
            from CFOP.motor_fiscal.fiscal import FiscalEngine
            fiscal_engine = FiscalEngine(banco=self.banco)
        except Exception:
            fiscal_engine = None

        itens = []
        for dto in dtos:
            item = dto.item_obj
            prod = item.produto
            if not prod:
                raise ValidationError(f"Produto do item {item.item_nume} não encontrado.")

            try:
                prod_id = int(item.item_prod)
            except (TypeError, ValueError):
                raise ValidationError(f"Produto inválido no item {item.item_nume}: {item.item_prod}")

            # Tentativa 1: usar tributos armazenados no item (se existirem)
            cst_icms = getattr(item, 'item_cst_icms', None) or getattr(item, 'item_cst', None)
            aliq_icms = getattr(item, 'item_aliq_icms', None) or getattr(item, 'item_aliq', None)
            cst_pis = getattr(item, 'item_cst_pis', None)
            aliq_pis = getattr(item, 'item_aliq_pis', None)
            cst_cofins = getattr(item, 'item_cst_cofins', None)
            aliq_cofins = getattr(item, 'item_aliq_cofins', None)
            cst_cbs = getattr(item, 'item_cst_cbs', None)
            aliq_cbs = getattr(item, 'item_aliq_cbs', None)
            cst_ibs = getattr(item, 'item_cst_ibs', None)
            aliq_ibs = getattr(item, 'item_aliq_ibs', None)
            cest = getattr(item, 'item_cest', None)

            # Se não existirem tributos no item, tentar resolver via fiscal padrao (produto/ncm/cfop)
            # Usar NCM do cadastro do produto (prod.prod_ncm) como fonte primária
            ncm_code = getattr(prod, 'prod_ncm', None) or getattr(item, 'item_ncm', None)
            uf_dest = getattr(cliente, 'enti_esta', None) if cliente else None

            if not any([cst_icms, aliq_icms, cst_pis, cst_cofins, cst_cbs, cst_ibs, cest]) and fiscal_engine:
                try:
                    fiscal_padrao, fonte = fiscal_engine.resolver_fiscal_padrao(
                        prod,
                        ncm_code,
                        None if not cfop else cfop,
                        uf_origem=None,
                        uf_destino=uf_dest,
                        tipo_entidade=None,
                        filial_id=self.filial,
                    )
                    if fiscal_padrao:
                        cst_icms = cst_icms or getattr(fiscal_padrao, 'cst_icms', None)
                        aliq_icms = aliq_icms or getattr(fiscal_padrao, 'aliq_icms', None)
                        cst_pis = cst_pis or getattr(fiscal_padrao, 'cst_pis', None)
                        aliq_pis = aliq_pis or getattr(fiscal_padrao, 'aliq_pis', None)
                        cst_cofins = cst_cofins or getattr(fiscal_padrao, 'cst_cofins', None)
                        aliq_cofins = aliq_cofins or getattr(fiscal_padrao, 'aliq_cofins', None)
                        cst_cbs = cst_cbs or getattr(fiscal_padrao, 'cst_cbs', None)
                        aliq_cbs = aliq_cbs or getattr(fiscal_padrao, 'aliq_cbs', None)
                        cst_ibs = cst_ibs or getattr(fiscal_padrao, 'cst_ibs', None)
                        aliq_ibs = aliq_ibs or getattr(fiscal_padrao, 'aliq_ibs', None)
                        if hasattr(fiscal_padrao, 'cest'):
                            cest = cest or getattr(fiscal_padrao, 'cest', None)
                except Exception:
                    # resolver fiscal falhou — seguir com valores nulos/fallbacks
                    pass

            # Normalização / conversões
            try:
                aliq_icms = float(aliq_icms) if aliq_icms is not None else None
            except Exception:
                aliq_icms = None
            try:
                aliq_pis = float(aliq_pis) if aliq_pis is not None else None
            except Exception:
                aliq_pis = None
            try:
                aliq_cofins = float(aliq_cofins) if aliq_cofins is not None else None
            except Exception:
                aliq_cofins = None
            try:
                aliq_cbs = float(aliq_cbs) if aliq_cbs is not None else None
            except Exception:
                aliq_cbs = None
            try:
                aliq_ibs = float(aliq_ibs) if aliq_ibs is not None else None
            except Exception:
                aliq_ibs = None

            itens.append({
                "produto": prod_id,
                "quantidade": float(dto.quantidade),
                "unitario": float(parse_decimal(item.item_unit or 0)),
                "desconto": float(parse_decimal(getattr(item, 'item_desc', 0) or 0)),
                "cfop": cfop,
                "ncm": ncm_code,
                "cest": cest,
                "cst_icms": str(cst_icms) if cst_icms is not None else None,
                "aliq_icms": aliq_icms,
                "cst_pis": str(cst_pis) if cst_pis is not None else None,
                "aliq_pis": aliq_pis,
                "cst_cofins": str(cst_cofins) if cst_cofins is not None else None,
                "aliq_cofins": aliq_cofins,
                "cst_cbs": str(cst_cbs) if cst_cbs is not None else None,
                "aliq_cbs": aliq_cbs,
                "cst_ibs": str(cst_ibs) if cst_ibs is not None else None,
                "aliq_ibs": aliq_ibs,
            })

        # Montar destinatário mínimo (esperado pelos validadores)
        destinatario_dict = {
            "documento": (getattr(cliente, 'enti_cnpj', None) or getattr(cliente, 'enti_cpf', None) or str(getattr(cliente, 'enti_clie', ''))),
            "uf": getattr(cliente, 'enti_esta', None) or getattr(self.pedido, 'pedi_esta', None) or '',
        }

        # Montar emitente mínimo (dados da filial/emitente)
        emitente_dict = None
        try:
            from Licencas.models import Filiais
            filial_obj = Filiais.objects.using(self.banco).defer('empr_cert_digi').filter(
                empr_empr=self.empresa, empr_codi=self.filial
            ).first()
            if filial_obj:
                emitente_dict = {
                    "cnpj": (getattr(filial_obj, 'empr_docu', '') or '').strip(),
                    "uf": getattr(filial_obj, 'empr_esta', '') or '',
                }
        except Exception:
            emitente_dict = None

        # Garantir formato dos itens compatível com validadores (codigo, descricao, quantidade, valor_unit)
        itens_payload = []
        missing_ncms = []
        for it in itens:
            # it currently contains produto (prod_id), quantidade, unitario, desconto, cfop, ncm etc.
            prod_obj = None
            try:
                from Produtos.models import Produtos
                prod_obj = Produtos.objects.using(self.banco).filter(prod_codi=str(it.get('produto'))).first()
            except Exception:
                prod_obj = None

            codigo = prod_obj.prod_codi if prod_obj else str(it.get('produto'))
            descricao = (getattr(prod_obj, 'prod_nome', None) or '') if prod_obj else ''

            ncm_val = it.get('ncm')
            if not ncm_val:
                missing_ncms.append(codigo)

            itens_payload.append({
                "codigo": codigo,
                "descricao": descricao or '',
                "quantidade": it.get('quantidade'),
                "valor_unit": it.get('unitario'),
                # repassa os campos fiscais se existirem
                "cfop": it.get('cfop'),
                "ncm": ncm_val,
                "cest": it.get('cest'),
                "cst_icms": it.get('cst_icms'),
                "aliq_icms": it.get('aliq_icms'),
                "cst_pis": it.get('cst_pis'),
                "aliq_pis": it.get('aliq_pis'),
                "cst_cofins": it.get('cst_cofins'),
                "aliq_cofins": it.get('aliq_cofins'),
                "cst_cbs": it.get('cst_cbs'),
                "aliq_cbs": it.get('aliq_cbs'),
                "cst_ibs": it.get('cst_ibs'),
                "aliq_ibs": it.get('aliq_ibs'),
            })

        if missing_ncms:
            # Normalizar erro: lançar ValidationError com mensagem clara sobre quais itens faltam NCM
            list_str = ', '.join(str(x) for x in missing_ncms)
            raise ValidationError(f"Itens sem NCM no pedido: {list_str}. Impossível emitir sem NCM.")

        payload = {
            "modelo": "55",
            "serie": "1",
            "numero": 0,
            "data_emissao": str(pedido.pedi_data),
            "data_saida": None,
            "tipo_operacao": 1,
            "finalidade": 1,
            "ambiente": 2,
            "emitente": emitente_dict,
            "destinatario": destinatario_dict,
            "itens": itens_payload,
            "tpag": tpag,
        }

        return payload

    # ------------------------------------------------------------------
    # Registra o que foi emitido e atualiza status do pedido
    # ------------------------------------------------------------------

    def _registrar_emissao(self, dtos: list[ItemEmissaoDTO]) -> None:
        """
        Incrementa item_quan_emit em cada item emitido e
        recalcula pedi_stat_nfe no pedido.
        """
        for dto in dtos:
            item = dto.item_obj
            atual = _quantidade_emitida(item)
            nova = atual + dto.quantidade

            # TODO: garantir que item_quan_emit existe no model e migration
            Itenspedidospisos.objects.using(self.banco).filter(
                item_empr=item.item_empr,
                item_fili=item.item_fili,
                item_pedi=item.item_pedi,
                item_nume=item.item_nume,
            ).update(item_quan_emit=nova)

        self._atualizar_status_pedido()

    def _atualizar_status_pedido(self) -> None:
        """
        Verifica se todos os itens estão totalmente emitidos.
        pedi_stat_nfe: 'N' → 'P' (parcial) ou 'E' (totalmente emitido)
        """
        itens = Itenspedidospisos.objects.using(self.banco).filter(
            item_empr=self.empresa,
            item_fili=self.filial,
            item_pedi=self.pedido.pedi_nume,
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
