from decimal import Decimal

from datetime import date
from django.db import transaction
from django.utils import timezone

from Pisos.models import Pedidospisos, Itenspedidospisos
from Pisos.services.utils_service import parse_decimal


class RomaneioEntregaService:
    @staticmethod
    def listar_itens(*, banco, pedido_numero, empresa=None, filial=None):
        if empresa is None or filial is None:
            raise ValueError("Parâmetros obrigatórios: empresa, filial.")

        filtros = {"item_pedi": int(pedido_numero)}
        filtros["item_empr"] = int(empresa)
        filtros["item_fili"] = int(filial)

        itens = (
            Itenspedidospisos.objects.using(banco)
            .filter(**filtros)
            .order_by("item_ambi", "item_nume")
        )

        saida = []
        for it in itens:
            quan_total = parse_decimal(getattr(it, "item_quan", None))
            quan_entr = parse_decimal(getattr(it, "item_quan_entr", None))
            quan_pend = max(quan_total - quan_entr, Decimal("0"))

            caix_total = parse_decimal(getattr(it, "item_caix", None))
            caix_entr = parse_decimal(getattr(it, "item_caix_entr", None))
            caix_pend = max(caix_total - caix_entr, Decimal("0"))

            # Formata data de entrega e número da nota (se houver)
            try:
                data_entr = getattr(it, "item_data_entr", None)
                item_data_entr = data_entr.isoformat() if data_entr is not None else ""
            except Exception:
                item_data_entr = str(getattr(it, "item_data_entr", "") or "")

            item_nfe_entr = getattr(it, "item_nfe_entr", None)
            item_nfe_entr = int(item_nfe_entr) if item_nfe_entr not in (None, "") else ""

            saida.append(
                {
                    "item_nume": getattr(it, "item_nume", None),
                    "item_ambi": getattr(it, "item_ambi", None),
                    "item_nome_ambi": (getattr(it, "item_nome_ambi", "") or "").strip(),
                    "item_prod": (getattr(it, "item_prod", "") or "").strip(),
                    "item_prod_nome": (getattr(it, "item_prod_nome", "") or "").strip(),
                    "item_quan": str(quan_total),
                    "item_quan_entr": str(quan_entr),
                    "item_quan_pend": str(quan_pend),
                    "item_caix": str(caix_total),
                    "item_caix_entr": str(caix_entr),
                    "item_caix_pend": str(caix_pend),
                    "item_data_entr": item_data_entr,
                    "item_nfe_entr": item_nfe_entr,
                }
            )

        return saida

    @staticmethod
    def entregar(
        *,
        banco,
        pedido_numero,
        empresa,
        filial,
        entregas,
        usuario_id=None,
        pedido_observacao=None,
    ):
        entregas = list(entregas or [])
        entregas_informadas = []
        for ent in entregas:
            try:
                item_nume = ent.get("item_nume")
            except Exception:
                item_nume = None
            qtd = parse_decimal((ent or {}).get("quantidade"))
            caix = parse_decimal((ent or {}).get("caixas"))
            if item_nume not in (None, "") and (qtd > 0 or caix > 0):
                entregas_informadas.append(ent)

        if not entregas_informadas:
            pendentes = RomaneioEntregaService.listar_itens(
                banco=banco,
                pedido_numero=pedido_numero,
                empresa=empresa,
                filial=filial,
            )
            auto = []
            for it in pendentes:
                qtd_pend = parse_decimal(it.get("item_quan_pend"))
                cx_pend = parse_decimal(it.get("item_caix_pend"))
                if qtd_pend > 0 or cx_pend > 0:
                    auto.append(
                        {
                            "item_nume": it.get("item_nume"),
                            "quantidade": str(qtd_pend),
                            "caixas": str(cx_pend),
                        }
                    )
            if not auto:
                raise ValueError("Nenhum item pendente para entrega.")
            entregas_informadas = auto

        usuario_id_int = None
        try:
            if usuario_id is not None and str(usuario_id).strip():
                usuario_id_int = int(usuario_id)
        except Exception:
            usuario_id_int = None

        with transaction.atomic(using=banco):
            if pedido_observacao is not None:
                pedido = (
                    Pedidospisos.objects.using(banco)
                    .filter(pedi_nume=int(pedido_numero), pedi_empr=int(empresa), pedi_fili=int(filial))
                    .first()
                )
                if pedido:
                    pedido.pedi_obse_roma = str(pedido_observacao or "").strip()
                    pedido.save(using=banco, update_fields=["pedi_obse_roma"])

            alterados = 0
            try:
                hoje = timezone.localdate()
            except Exception:
                try:
                    hoje = timezone.now().date()
                except Exception:
                    hoje = date.today()
            tolerancia = Decimal("0.01")

            for ent in entregas_informadas:
                item_nume = ent.get("item_nume")
                if item_nume in (None, ""):
                    raise ValueError("Item inválido.")

                qtd = parse_decimal(ent.get("quantidade"))
                caix = parse_decimal(ent.get("caixas"))

                item = (
                    Itenspedidospisos.objects.using(banco)
                    .filter(
                        item_nume=int(item_nume),
                        item_pedi=int(pedido_numero),
                        item_empr=int(empresa),
                        item_fili=int(filial),
                    )
                    .first()
                )
                if not item:
                    raise ValueError(f"Item {item_nume} não encontrado no pedido {pedido_numero}.")

                quan_total = parse_decimal(getattr(item, "item_quan", None))
                quan_entr = parse_decimal(getattr(item, "item_quan_entr", None))
                quan_pend = max(quan_total - quan_entr, Decimal("0"))

                caix_total = parse_decimal(getattr(item, "item_caix", None))
                caix_entr = parse_decimal(getattr(item, "item_caix_entr", None))
                caix_pend = max(caix_total - caix_entr, Decimal("0"))

                if qtd > quan_pend:
                    if (qtd - quan_pend) <= tolerancia:
                        qtd = quan_pend
                    else:
                        raise ValueError(
                            f"Quantidade a entregar ({qtd}) maior que a pendente ({quan_pend}) no item {item_nume}."
                        )

                if caix > caix_pend:
                    if (caix - caix_pend) <= tolerancia:
                        caix = caix_pend
                    else:
                        raise ValueError(
                            f"Caixas a entregar ({caix}) maior que a pendente ({caix_pend}) no item {item_nume}."
                        )

                novo_quan_entr = quan_entr + max(qtd, Decimal("0"))
                novo_caix_entr = caix_entr + max(caix, Decimal("0"))

                item.item_quan_entr = novo_quan_entr
                item.item_caix_entr = novo_caix_entr
                item.item_stat_manu_data = hoje
                # Preencher data de entrega do item
                try:
                    item.item_data_entr = hoje
                except Exception:
                    pass

                if usuario_id_int is not None:
                    item.item_stat_manu_user = usuario_id_int

                completo_quan = quan_total > 0 and novo_quan_entr >= quan_total
                completo_caix = caix_total <= 0 or novo_caix_entr >= caix_total
                item.item_stat_manu = "ENTREGUE" if (completo_quan and completo_caix) else "ENTREGA PARCIAL"

                # Se a entrega informar número da nota, preencher item_nfe_entr
                nfe_num = None
                if isinstance(ent, dict):
                    for key in ("nfe_numero", "nfe", "nota_numero", "numero_nfe", "item_nfe_entr"):
                        if key in ent and ent.get(key) not in (None, ""):
                            try:
                                nfe_num = int(ent.get(key))
                                break
                            except Exception:
                                nfe_num = ent.get(key)
                                break

                update_fields = [
                    "item_quan_entr",
                    "item_caix_entr",
                    "item_stat_manu_data",
                    "item_stat_manu_user",
                    "item_stat_manu",
                    "item_data_entr",
                ]

                if nfe_num is not None:
                    try:
                        item.item_nfe_entr = nfe_num
                        update_fields.append("item_nfe_entr")
                    except Exception:
                        pass

                item.save(
                    using=banco,
                    update_fields=update_fields,
                )
                alterados += 1

            if alterados == 0:
                raise ValueError("Informe uma quantidade/caixa maior que zero para entregar.")

            return {"itens_alterados": alterados, "data": hoje.isoformat()}
