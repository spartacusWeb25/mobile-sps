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
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from Pisos.models import Pedidospisos, Itenspedidospisos
from Pisos.services.utils_service import parse_decimal
from Notas_Fiscais.emissao.emissao_nota_service import EmissaoNotaService
from Notas_Fiscais.services.cobranca_origem_service import CobrancaOrigemService

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

    def emitir(self, itens_emitir: list[dict] | None = None) -> dict:
        """
        itens_emitir = [{"item_nume": 1, "quantidade": 5}, ...]
        Retorna o dict de resultado de EmissaoNotaService.emitir_nota.
        """
        with transaction.atomic(using=self.banco):
            itens_db = self._carregar_itens()

            dtos = self._resolver_quantidades(itens_db, itens_emitir)

            if not dtos:
                raise ValidationError("Nenhum item com saldo disponível para emissão.")

            nota_data, itens_payload = self._montar_nota_data(dtos)

            from Notas_Fiscais.services.nota_service import NotaService
            from Notas_Fiscais.aplicacao.emissao_service import EmissaoService

            nota = None
            try:
                nota = NotaService.criar(
                    data=nota_data,
                    itens=itens_payload,
                    impostos_map=None,
                    transporte=None,
                    empresa=self.empresa,
                    filial=self.filial,
                    database=self.banco,
                )
            except Exception as e:
                raise ValidationError(f"Erro ao criar nota rascunho: {e}")

            try:
                emissor = EmissaoService(slug=self.banco, database=self.banco)
                resposta = emissor.emitir(nota.id)
            except Exception as e:
                raise ValidationError(f"Falha ao emitir NF-e: {e}")

            status_sefaz = resposta.get("status")
            if str(status_sefaz) in ("100", "204"):
                nota_numero = getattr(nota, "numero", None) if nota is not None else None
                try:
                    nota_numero = int(nota_numero) if nota_numero not in (None, "") else None
                except Exception:
                    pass

                self._registrar_emissao(dtos, nota_numero=nota_numero, sefaz_resposta=resposta)

            return {"sefaz": resposta}

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
    # FIX 1: Carrega TODOS os campos dos itens — sem .only() restritivo.
    # O .only() anterior omitia item_ncm, item_desc, item_cst_icms, etc.,
    # causando ValidationError("Itens sem NCM...") antes mesmo de chegar na SEFAZ.
    # ------------------------------------------------------------------

    def _carregar_itens(self) -> dict[int, Itenspedidospisos]:
        qs = Itenspedidospisos.objects.using(self.banco).filter(
            item_empr=self.empresa,
            item_fili=self.filial,
            item_pedi=self.pedido.pedi_nume,
        )
        # Não usar .only() aqui: campos fiscais (ncm, cst, aliq, desc, etc.)
        # precisam estar disponíveis em _montar_nota_data sem queries adicionais.

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
                )
                produtos_map = {(str(p.prod_empr), str(p.prod_codi)): p for p in produtos_qs}
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
    # FIX 2: _montar_nota_data — loop único, sem reprocessamento redundante.
    # O código original construía `itens` com chave "produto" e depois
    # reconstruía `itens_payload` com chave "codigo" relendo o banco de novo.
    # Agora: um único loop já usa o produto pré-carregado em _carregar_itens.
    # ------------------------------------------------------------------

    def _montar_nota_data(self, dtos: list[ItemEmissaoDTO]) -> tuple:  # retorna (nota_data, itens_payload)
        pedido = self.pedido

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

        uf_dest = getattr(cliente, 'enti_esta', None)

        itens_payload = []
        missing_ncms = []

        info_partes = [f"Pedido: {pedido.pedi_nume}"]
        if getattr(pedido, "pedi_ende", None):
            endereco = f"{pedido.pedi_ende}"
            if getattr(pedido, "pedi_nume_ende", None):
                endereco += f" N.{pedido.pedi_nume_ende}"
            info_partes.append(f"ENDERECO: {endereco}")
        if getattr(pedido, "pedi_cida", None) or getattr(pedido, "pedi_esta", None):
            info_partes.append(
                f"CIDADE: {(getattr(pedido, 'pedi_cida', '') or '').strip()} - {(getattr(pedido, 'pedi_esta', '') or '').strip()}"
            )
        if getattr(pedido, "pedi_bair", None):
            info_partes.append(f"BAIRRO: {pedido.pedi_bair}")
        if getattr(pedido, "pedi_comp", None):
            info_partes.append(f"COMPLEMENTO: {pedido.pedi_comp}")
        if getattr(pedido, "pedi_obse_roma", None):
            info_partes.append(str(getattr(pedido, "pedi_obse_roma") or "").strip())
        if getattr(pedido, "pedi_obse", None):
            info_partes.append(str(getattr(pedido, "pedi_obse") or "").strip())
        if getattr(cliente, "enti_clie", None):
            info_partes.append(f"Cliente: {cliente.enti_clie}")
        informacoes_nota = "| ".join([p for p in info_partes if str(p or "").strip()])

        for dto in dtos:
            item = dto.item_obj
            # Usa o produto pré-carregado em _carregar_itens — sem nova query ao banco
            prod = item.produto
            if not prod:
                raise ValidationError(f"Produto do item {item.item_nume} não encontrado.")

            # Campos fiscais direto do item (todos disponíveis pois removemos .only())
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

            # NCM: item primeiro, fallback para cadastro do produto
            ncm_code = getattr(item, 'item_ncm', None) or getattr(prod, 'prod_ncm', None)

            # Se não tiver tributos no item, resolve via FiscalEngine
            if not any([cst_icms, aliq_icms, cst_pis, cst_cofins, cst_cbs, cst_ibs, cest]) and fiscal_engine:
                try:
                    fiscal_padrao, _ = fiscal_engine.resolver_fiscal_padrao(
                        prod,
                        ncm_code,
                        cfop,
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
                        cest = cest or getattr(fiscal_padrao, 'cest', None)
                except Exception:
                    pass  # Segue com os valores disponíveis

            # Normaliza alíquotas para float
            def _to_float(v):
                try:
                    return float(v) if v is not None else None
                except Exception:
                    return None

            if not ncm_code:
                missing_ncms.append(prod.prod_codi)

            itens_payload.append({
                "codigo": str(prod.prod_codi),
                "descricao": getattr(prod, 'prod_nome', '') or '',
                "quantidade": float(dto.quantidade),
                "valor_unit": float(parse_decimal(item.item_unit or 0)),
                "desconto": float(parse_decimal(getattr(item, 'item_desc', 0) or 0)),
                "cfop": cfop,
                "ncm": ncm_code,
                "cest": cest,
                "cst_icms": str(cst_icms) if cst_icms is not None else None,
                "aliq_icms": _to_float(aliq_icms),
                "cst_pis": str(cst_pis) if cst_pis is not None else None,
                "aliq_pis": _to_float(aliq_pis),
                "cst_cofins": str(cst_cofins) if cst_cofins is not None else None,
                "aliq_cofins": _to_float(aliq_cofins),
                "cst_cbs": str(cst_cbs) if cst_cbs is not None else None,
                "aliq_cbs": _to_float(aliq_cbs),
                "cst_ibs": str(cst_ibs) if cst_ibs is not None else None,
                "aliq_ibs": _to_float(aliq_ibs),
                "numero_pedido": str(pedido.pedi_nume),
                "numero_item_pedido": int(getattr(item, "item_nume", 0) or 0),
                "informacoes_adicionais": f"Pedido: {pedido.pedi_nume} Item: {int(getattr(item, 'item_nume', 0) or 0)}",
            })

        if missing_ncms:
            list_str = ', '.join(str(x) for x in missing_ncms)
            raise ValidationError(f"Itens sem NCM no pedido: {list_str}. Impossível emitir sem NCM.")

        # Destinatário
        documento_raw = (
            getattr(cliente, 'enti_cnpj', None)
            or getattr(cliente, 'enti_cpf', None)
            or str(getattr(cliente, 'enti_clie', ''))
        )
        from Entidades.services.validacao_documentos import DocumentoFiscalValidacaoServico
        documento_digits = DocumentoFiscalValidacaoServico.somente_digitos(documento_raw)

        if documento_digits:
            if len(documento_digits) == 11:
                if not DocumentoFiscalValidacaoServico.cpf_valido(documento_digits):
                    raise ValidationError("CPF do destinatário inválido.")
            elif len(documento_digits) == 14:
                try:
                    DocumentoFiscalValidacaoServico.validar_cnpj(documento_digits, campo="documento")
                except Exception:
                    raise ValidationError("CNPJ do destinatário inválido.")

        destinatario_dict = {
            "documento": documento_digits or documento_raw,
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

        payload = {
            "modelo": "55",
            "serie": "1",
            "numero": 0,
            "data_emissao": datetime.now().strftime('%Y-%m-%d'),
            "data_saida": datetime.now().strftime('%Y-%m-%d'),
            "tipo_operacao": 1,
            "finalidade": 1,
            "ambiente": 2,
            "pedido_origem": str(pedido.pedi_nume),
            "informacoes_adicionais": informacoes_nota,
            "emitente": emitente_dict,
            "destinatario": cliente,  # passar a instância/ID do Entidades (NotaService aceita Entidades ou ID)
            "itens": itens_payload,
            #"tpag": 0,
        }
        payload = CobrancaOrigemService.aplicar_no_payload(
            payload=payload,
            cobranca=CobrancaOrigemService.from_pedido_pisos(pedido=pedido, banco=self.banco),
        )

        return payload, itens_payload

    # ------------------------------------------------------------------
    # FIX 3: _registrar_emissao — atualiza saldos em memória antes de
    # chamar _atualizar_status_pedido, evitando re-leitura inconsistente
    # do banco quando item_quan_emit ainda não foi commitado.
    # ------------------------------------------------------------------

    def _registrar_emissao(self, dtos: list[ItemEmissaoDTO], nota_numero=None, sefaz_resposta: dict | None = None) -> None:
        """
        Incrementa item_quan_emit em cada item emitido e
        recalcula pedi_stat_nfe no pedido.
        """
        novos_saldos: dict[int, Decimal] = {}

        for dto in dtos:
            item = dto.item_obj
            atual = _quantidade_emitida(item)
            nova = atual + dto.quantidade

            # Atualiza campo de quantidade emitida
            Itenspedidospisos.objects.using(self.banco).filter(
                item_empr=item.item_empr,
                item_fili=item.item_fili,
                item_pedi=item.item_pedi,
                item_nume=item.item_nume,
            ).update(item_quan_emit=nova)

            # Se recebemos número da nota emitida, setar item_nfe_fatu (faturamento)
            if nota_numero is not None:
                try:
                    Itenspedidospisos.objects.using(self.banco).filter(
                        item_empr=item.item_empr,
                        item_fili=item.item_fili,
                        item_pedi=item.item_pedi,
                        item_nume=item.item_nume,
                    ).update(item_nfe_fatu=nota_numero)
                except Exception:
                    pass

            # Atualiza o objeto em memória para que _atualizar_status_pedido
            # não precise re-ler do banco com valores ainda não visíveis
            item.item_quan_emit = nova
            total = parse_decimal(item.item_quan or 0)
            novos_saldos[item.item_nume] = max(total - nova, Decimal("0"))

        # Se quisermos, também podemos guardar outras informações da resposta SEFAZ
        if sefaz_resposta is not None:
            try:
                # Se a resposta traz 'chave' e 'protocolo', armazená-los no pedido
                chave = sefaz_resposta.get("chave")
                protocolo = sefaz_resposta.get("protocolo")
                if chave or protocolo:
                    Pedidospisos.objects.using(self.banco).filter(
                        pedi_empr=self.empresa,
                        pedi_fili=self.filial,
                        pedi_nume=self.pedido.pedi_nume,
                    ).update(
                        **({"pedi_nfev": nota_numero} if nota_numero is not None else {}),
                    )
            except Exception:
                pass

        self._atualizar_status_pedido(novos_saldos)

    def _atualizar_status_pedido(self, saldos_em_memoria: dict[int, Decimal] | None = None) -> None:
        """
        Verifica se todos os itens estão totalmente emitidos.
        pedi_stat_nfe: 'N' → 'P' (parcial) ou 'E' (totalmente emitido)

        saldos_em_memoria: dict {item_nume: saldo_restante} calculado em
        _registrar_emissao para evitar race condition com o .update() anterior.
        """
        if saldos_em_memoria is not None:
            # Usa os valores já calculados em memória — evita re-leitura inconsistente
            totalmente_emitido = all(s == 0 for s in saldos_em_memoria.values())
        else:
            # Fallback: re-lê do banco (útil se chamado isoladamente)
            itens = Itenspedidospisos.objects.using(self.banco).filter(
                item_empr=self.empresa,
                item_fili=self.filial,
                item_pedi=self.pedido.pedi_nume,
            )
            totalmente_emitido = all(_saldo_disponivel(i) == 0 for i in itens)

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
