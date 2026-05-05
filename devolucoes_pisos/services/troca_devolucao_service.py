from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import json
import logging

from django.db import transaction
from django.db.models import Max

from Pisos.models import Pedidospisos, Itenspedidospisos
from ..models import Devolucoespedidopiso, Itensdevolucoespisos, Creditotrocas

logger = logging.getLogger(__name__)


class DevolucaoPedidoPisoService:
    OBSE_REPO_PREFIX = "SPS_REPO:"

    @staticmethod
    def _to_decimal(value, default: str = "0") -> Decimal:
        try:
            if value is None:
                return Decimal(default)
            if isinstance(value, Decimal):
                return value
            if isinstance(value, (int, float)):
                return Decimal(str(value))
            s = str(value).strip().replace(",", ".")
            if not s:
                return Decimal(default)
            return Decimal(s)
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    @staticmethod
    def listar(banco, filtros=None):
        filtros = filtros or {}
        qs = Devolucoespedidopiso.objects.using(banco).all().order_by("-devo_data", "-devo_pedi")

        devo_empr = filtros.get("devo_empr")
        devo_fili = filtros.get("devo_fili")
        devo_pedi = filtros.get("devo_pedi")
        devo_data = filtros.get("devo_data")

        if devo_empr not in (None, ""):
            qs = qs.filter(devo_empr=devo_empr)
        if devo_fili not in (None, ""):
            qs = qs.filter(devo_fili=devo_fili)
        if devo_pedi not in (None, ""):
            qs = qs.filter(devo_pedi=devo_pedi)
        if devo_data not in (None, ""):
            qs = qs.filter(devo_data=devo_data)

        return qs

    @staticmethod
    def obter_devolucao(banco, pedido_numero: int) -> Devolucoespedidopiso | None:
        try:
            return Devolucoespedidopiso.objects.using(banco).filter(devo_pedi=pedido_numero).first()
        except Exception:
            return None

    @staticmethod
    def obter_itens_devolucao(banco, empresa: int, filial: int, pedido_numero: int):
        return (
            Itensdevolucoespisos.objects.using(banco)
            .filter(item_empr=empresa, item_fili=filial, item_pedi=pedido_numero)
            .order_by("item_ambi", "item_nume")
        )

    @staticmethod
    def _proximo_item_nume(banco) -> int:
        ultimo = (
            Itensdevolucoespisos.objects.using(banco).aggregate(mx=Max("item_nume")).get("mx") or 0
        )
        try:
            return int(ultimo) + 1
        except Exception:
            return 1

    @staticmethod
    def extrair_reposicao_de_obse(item_obse: str | None) -> dict:
        obse = (item_obse or "").strip()
        if not obse.startswith(DevolucaoPedidoPisoService.OBSE_REPO_PREFIX):
            return {}
        payload = obse[len(DevolucaoPedidoPisoService.OBSE_REPO_PREFIX) :].strip()
        try:
            data = json.loads(payload)
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            "repo_prod": data.get("repo_prod"),
            "repo_desc": data.get("repo_desc"),
            "repo_quan": data.get("repo_quan"),
            "repo_unit": data.get("repo_unit"),
            "repo_total": data.get("repo_total"),
            "obse": data.get("obse"),
        }

    @staticmethod
    def _montar_obse_com_reposicao(*, obse_original: str | None, repo: dict | None) -> str | None:
        if not repo:
            return obse_original
        repo_prod = str(repo.get("repo_prod") or "").strip()
        if not repo_prod:
            return obse_original
        data = {
            "repo_prod": repo_prod,
            "repo_desc": str(repo.get("repo_desc") or "").strip() or None,
            "repo_quan": repo.get("repo_quan"),
            "repo_unit": repo.get("repo_unit"),
            "repo_total": repo.get("repo_total"),
            "obse": (obse_original or "").strip() or None,
        }
        return f"{DevolucaoPedidoPisoService.OBSE_REPO_PREFIX}{json.dumps(data, ensure_ascii=False)}"
    
    @staticmethod
    def _proximo_entrada_sequ(banco) -> int:
        from Entradas_Estoque.models import EntradaEstoque

        ultimo = EntradaEstoque.objects.using(banco).aggregate(mx=Max("entr_sequ")).get("mx") or 0
        try:
            return int(ultimo) + 1
        except Exception:
            return 1

    @staticmethod
    def _carregar_pedido_original(banco, pedido_numero: int) -> Pedidospisos:
        pedido = Pedidospisos.objects.using(banco).filter(pedi_nume=pedido_numero).first()
        if not pedido:
            raise ValueError("Pedido de pisos não encontrado.")
        return pedido

    @staticmethod
    def _carregar_itens_pedido_original(banco, empresa: int, filial: int, pedido_numero: int):
        return list(
            Itenspedidospisos.objects.using(banco)
            .filter(item_empr=empresa, item_fili=filial, item_pedi=pedido_numero)
            .order_by("item_ambi", "item_nume")
        )

    @staticmethod
    def _normalizar_itens_payload(itens: list[dict] | None) -> list[dict]:
        if not itens:
            return []
        if not isinstance(itens, list):
            return []
        norm = []
        for it in itens:
            if isinstance(it, dict):
                norm.append(it)
        return norm

    @staticmethod
    def _validar_e_mapear_itens(
        *,
        itens_payload: list[dict] | None,
        itens_pedido: list[Itenspedidospisos],
    ) -> list[dict]:
        itens_payload = DevolucaoPedidoPisoService._normalizar_itens_payload(itens_payload)

        original_map = {}
        for it in itens_pedido:
            chave = (int(getattr(it, "item_ambi") or 0), str(getattr(it, "item_prod") or "").strip())
            original_map[chave] = it

        if not itens_payload:
            result = []
            for it in itens_pedido:
                result.append(
                    {
                        "item_ambi": int(it.item_ambi or 0),
                        "item_prod": str(it.item_prod or "").strip(),
                        "item_m2": it.item_m2,
                        "item_quan": it.item_quan,
                        "item_unit": it.item_unit,
                        "item_suto": it.item_suto,
                        "item_obse": it.item_obse,
                        "item_nome_ambi": getattr(it, "item_nome_ambi", None),
                        "item_desc": getattr(it, "item_desc", None),
                        "item_queb": getattr(it, "item_queb", None),
                        "item_prod_nome": getattr(it, "item_prod_nome", None),
                    }
                )
            return result

        result = []
        for it in itens_payload:
            if it.get("selecionado") in (False, "false", "0", 0):
                continue
            ambi = int(it.get("item_ambi") or 0)
            prod = str(it.get("item_prod") or "").strip()
            if not prod:
                continue

            chave = (ambi, prod)
            original = original_map.get(chave)
            if not original:
                raise ValueError(f"Item inválido para devolução: ambiente={ambi} produto={prod}.")

            qtd_original = DevolucaoPedidoPisoService._to_decimal(getattr(original, "item_quan", 0) or 0)
            qtd_devol = DevolucaoPedidoPisoService._to_decimal(it.get("item_quan"), default=str(qtd_original))

            if qtd_devol < 0:
                raise ValueError(f"Quantidade inválida para o produto {prod}.")
            if qtd_devol > qtd_original:
                raise ValueError(f"Quantidade devolvida maior que a do pedido para o produto {prod}.")

            unit = DevolucaoPedidoPisoService._to_decimal(it.get("item_unit"), default=str(getattr(original, "item_unit", 0) or 0))
            suto = DevolucaoPedidoPisoService._to_decimal(it.get("item_suto"), default=str(unit * qtd_devol))
            desc = DevolucaoPedidoPisoService._to_decimal(it.get("item_desc"), default=str(getattr(original, "item_desc", 0) or 0))
            m2 = it.get("item_m2", getattr(original, "item_m2", None))

            repo_prod = str(it.get("repo_prod") or "").strip()
            repo_quan = DevolucaoPedidoPisoService._to_decimal(it.get("repo_quan"), default="0")
            repo_unit = DevolucaoPedidoPisoService._to_decimal(it.get("repo_unit"), default="0")
            repo_total = DevolucaoPedidoPisoService._to_decimal(it.get("repo_total"), default=str(repo_quan * repo_unit))

            result.append(
                {
                    "item_ambi": ambi,
                    "item_prod": prod,
                    "item_m2": m2,
                    "item_quan": qtd_devol,
                    "item_unit": unit,
                    "item_suto": suto,
                    "item_obse": it.get("item_obse", getattr(original, "item_obse", None)),
                    "item_nome_ambi": it.get("item_nome_ambi", getattr(original, "item_nome_ambi", None)),
                    "item_desc": desc,
                    "item_queb": it.get("item_queb", getattr(original, "item_queb", None)),
                    "item_prod_nome": it.get("item_prod_nome", getattr(original, "item_prod_nome", None)),
                    "repo_prod": repo_prod or None,
                    "repo_desc": str(it.get("repo_desc") or "").strip() or None,
                    "repo_quan": repo_quan,
                    "repo_unit": repo_unit,
                    "repo_total": repo_total,
                }
            )
        return result

    @staticmethod
    def _calcular_credito(itens: list[dict], desconto: Decimal, tipo: str) -> Decimal:
        total = Decimal("0.00")
        total_repo = Decimal("0.00")
        for it in itens or []:
            suto = DevolucaoPedidoPisoService._to_decimal(it.get("item_suto"), default="0")
            desc = DevolucaoPedidoPisoService._to_decimal(it.get("item_desc"), default="0")
            total += (suto - desc)
            if str(tipo) == "TROC":
                total_repo += DevolucaoPedidoPisoService._to_decimal(it.get("repo_total"), default="0")
        if str(tipo) == "TROC":
            total -= total_repo
        total -= (desconto or Decimal("0.00"))
        if total < 0:
            total = Decimal("0.00")
        return total.quantize(Decimal("0.01"))
    
    @staticmethod
    def _calcular_totais(itens: list[dict]) -> tuple[Decimal, Decimal]:
        total_devo = Decimal("0.00")
        total_repo = Decimal("0.00")
        for it in itens or []:
            suto = DevolucaoPedidoPisoService._to_decimal(it.get("item_suto"), default="0")
            desc = DevolucaoPedidoPisoService._to_decimal(it.get("item_desc"), default="0")
            total_devo += (suto - desc)
            total_repo += DevolucaoPedidoPisoService._to_decimal(it.get("repo_total"), default="0")
        return total_devo, total_repo

    @staticmethod
    def criar_ou_atualizar_por_pedido(
        *,
        banco,
        pedido_numero: int,
        usuario: int | None,
        tipo: str = "DEVO",
        desconto: Decimal | str | int | float | None = None,
        data_devolucao: date | None = None,
        itens: list[dict] | None = None,
    ) -> Devolucoespedidopiso:
        pedido_numero = int(pedido_numero)
        pedido = DevolucaoPedidoPisoService._carregar_pedido_original(banco, pedido_numero)
        empresa = int(pedido.pedi_empr or 0)
        filial = int(pedido.pedi_fili or 0)

        if not empresa or not filial:
            raise ValueError("Pedido de pisos sem empresa/filial válida.")

        if itens is None:
            devolucao_atual = DevolucaoPedidoPisoService.obter_devolucao(banco, pedido_numero)
            if devolucao_atual:
                itens_atuais = DevolucaoPedidoPisoService.obter_itens_devolucao(
                    banco, empresa, filial, pedido_numero
                )
                itens = [
                    {
                        "item_ambi": it.item_ambi,
                        "item_prod": it.item_prod,
                        "item_m2": it.item_m2,
                        "item_quan": it.item_quan,
                        "item_unit": it.item_unit,
                        "item_suto": it.item_suto,
                        "item_desc": it.item_desc,
                        "item_obse": it.item_obse,
                        "item_nome_ambi": it.item_nome_ambi,
                        "item_prod_nome": it.item_prod_nome,
                        "item_queb": it.item_queb,
                        **DevolucaoPedidoPisoService.extrair_reposicao_de_obse(it.item_obse),
                    }
                    for it in itens_atuais
                ]

        itens_pedido = DevolucaoPedidoPisoService._carregar_itens_pedido_original(
            banco, empresa, filial, pedido_numero
        )
        itens_map = DevolucaoPedidoPisoService._validar_e_mapear_itens(
            itens_payload=itens, itens_pedido=itens_pedido
        )

        desconto_dec = DevolucaoPedidoPisoService._to_decimal(desconto, default="0.00")
        tipo_norm = str(tipo or "DEVO").strip().upper()
        if tipo_norm not in ("DEVO", "TROC"):
            tipo_norm = "DEVO"
        total_devo, total_repo = DevolucaoPedidoPisoService._calcular_totais(itens_map)
        valor_credito = DevolucaoPedidoPisoService._calcular_credito(itens_map, desconto_dec, tipo_norm)
        valor_receber = Decimal("0.00")
        if tipo_norm == "TROC":
            valor_receber = (total_repo + desconto_dec) - total_devo
            if valor_receber < 0:
                valor_receber = Decimal("0.00")
            valor_receber = valor_receber.quantize(Decimal("0.01"))

        dt = data_devolucao or date.today()

        with transaction.atomic(using=banco):
            devolucao, _ = Devolucoespedidopiso.objects.using(banco).update_or_create(
                devo_pedi=pedido_numero,
                defaults={
                    "devo_empr": empresa,
                    "devo_fili": filial,
                    "devo_data": dt,
                    "devo_usua": usuario,
                    "devo_desc": desconto_dec,
                    "devo_titu": str(pedido_numero)[:13],
                },
            )

            Itensdevolucoespisos.objects.using(banco).filter(
                item_empr=empresa, item_fili=filial, item_pedi=pedido_numero
            ).delete()

            proximo_item_nume = DevolucaoPedidoPisoService._proximo_item_nume(banco)
            proximo_ctrl_entr = DevolucaoPedidoPisoService._proximo_entrada_sequ(banco)
            ctrl_entr_inicial = proximo_ctrl_entr if itens_map else None

            ent_enti = str(pedido.pedi_clie or "").strip()[:10] or None
            obs_base = f"{('Troca' if tipo_norm == 'TROC' else 'Devolução')} Pisos {pedido_numero}"
            ctrl_values = []
            for it in itens_map:
                repo = {
                    "repo_prod": it.get("repo_prod"),
                    "repo_desc": it.get("repo_desc"),
                    "repo_quan": str(it.get("repo_quan") or ""),
                    "repo_unit": str(it.get("repo_unit") or ""),
                    "repo_total": str(it.get("repo_total") or ""),
                }
                item_obse = it.get("item_obse")
                if tipo_norm == "TROC":
                    item_obse = DevolucaoPedidoPisoService._montar_obse_com_reposicao(
                        obse_original=item_obse,
                        repo=repo,
                    )
                if not item_obse:
                    item_obse = obs_base
                Itensdevolucoespisos.objects.using(banco).create(
                    item_nume=proximo_item_nume,
                    item_empr=empresa,
                    item_fili=filial,
                    item_pedi=pedido_numero,
                    item_ambi=it["item_ambi"],
                    item_prod=it["item_prod"],
                    item_m2=it.get("item_m2"),
                    item_quan=it.get("item_quan"),
                    item_unit=it.get("item_unit"),
                    item_suto=it.get("item_suto"),
                    item_obse=item_obse,
                    item_nome_ambi=it.get("item_nome_ambi"),
                    item_desc=it.get("item_desc"),
                    item_queb=it.get("item_queb"),
                    item_prod_nome=it.get("item_prod_nome"),
                    item_devo_data=dt,
                    item_ctrl_entr=proximo_ctrl_entr,
                )
                ctrl_values.append(proximo_ctrl_entr)
                proximo_item_nume += 1
                proximo_ctrl_entr += 1

            if ctrl_entr_inicial is not None and getattr(devolucao, "devo_entr_ctrl", None) != ctrl_entr_inicial:
                devolucao.devo_entr_ctrl = ctrl_entr_inicial
                devolucao.save(using=banco, update_fields=["devo_entr_ctrl"])

            try:
                from Entradas_Estoque.models import EntradaEstoque

                if ctrl_values:
                    EntradaEstoque.objects.using(banco).filter(
                        entr_empr=empresa,
                        entr_fili=filial,
                        entr_sequ__in=ctrl_values,
                    ).update(
                        entr_enti=ent_enti,
                        entr_obse=obs_base,
                        entr_usua=int(usuario or 1),
                    )
            except Exception:
                pass

            obs = f"Crédito {('troca' if tipo_norm == 'TROC' else 'devolução')} (Pisos) do pedido {pedido_numero}"
            credito_existente_id = getattr(devolucao, "devo_cred", None)

            if credito_existente_id:
                existe_credito = Creditotrocas.objects.using(banco).filter(cred_id=credito_existente_id).exists()
                if existe_credito:
                    Creditotrocas.objects.using(banco).filter(cred_id=credito_existente_id).update(
                        cred_fina_empr=empresa,
                        cred_fina_fili=filial,
                        cred_fina_clie=int(pedido.pedi_clie or 0),
                        cred_fina_vend=int(pedido.pedi_vend or 0),
                        cred_fina_data=dt,
                        cred_fina_es=1,
                        cred_fina_valo=valor_credito,
                        cred_fina_obse=obs[:150],
                    )
                    credito_id = credito_existente_id
                else:
                    credito_existente_id = None

            if not credito_existente_id:
                credito = Creditotrocas.objects.using(banco).create(
                    cred_fina_empr=empresa,
                    cred_fina_fili=filial,
                    cred_fina_clie=int(pedido.pedi_clie or 0),
                    cred_fina_vend=int(pedido.pedi_vend or 0),
                    cred_fina_data=dt,
                    cred_fina_es=1,
                    cred_fina_valo=valor_credito,
                    cred_fina_obse=obs[:150],
                )
                credito_id = credito.cred_id

            if getattr(devolucao, "devo_cred", None) != credito_id:
                devolucao.devo_cred = credito_id
                devolucao.save(using=banco, update_fields=["devo_cred"])

            if tipo_norm == "TROC" and valor_receber > 0:
                from contas_a_receber.models import Titulosreceber
                from contas_a_receber.services import criar_titulo_receber, atualizar_titulo_receber

                titulo_numero = f"TP{pedido_numero:011d}"[-13:]
                titulo_serie = "TPIS"
                titulo_parc = "1"

                dados_titulo = {
                    "titu_empr": empresa,
                    "titu_fili": filial,
                    "titu_clie": int(pedido.pedi_clie or 0),
                    "titu_titu": titulo_numero,
                    "titu_seri": titulo_serie,
                    "titu_parc": titulo_parc,
                    "titu_emis": dt,
                    "titu_venc": dt,
                    "titu_valo": valor_receber,
                    "titu_hist": f"Troca Pisos pedido {pedido_numero} - diferença reposição",
                    "titu_vend": int(pedido.pedi_vend or 0) or None,
                    "titu_situ": 1,
                    "titu_tipo": "Receber",
                }

                existente = (
                    Titulosreceber.objects.using(banco)
                    .filter(
                        titu_empr=empresa,
                        titu_fili=filial,
                        titu_clie=int(pedido.pedi_clie or 0),
                        titu_titu=titulo_numero,
                        titu_seri=titulo_serie,
                        titu_parc=titulo_parc,
                    )
                    .first()
                )
                if existente:
                    atualizar_titulo_receber(existente, banco=banco, dados={"titu_valo": valor_receber, "titu_hist": dados_titulo["titu_hist"]})
                else:
                    criar_titulo_receber(banco=banco, dados=dados_titulo, empresa_id=empresa, filial_id=filial)

                if getattr(devolucao, "devo_titu", None) != titulo_numero:
                    devolucao.devo_titu = titulo_numero
                    devolucao.save(using=banco, update_fields=["devo_titu"])

        return devolucao
