from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.core.exceptions import ValidationError

from Pisos.models import Pedidospisos, Itenspedidospisos
from Pisos.services.utils_service import parse_decimal, arredondar
from Pisos.services.cliente_service import ClienteEnderecoService
from Pisos.services.credito_troca_service import CreditoTrocaPisosService
from Produtos.models import Produtos
from contas_a_receber.models import Titulosreceber
from contas_a_receber.services import criar_titulo_receber


class PedidoCriarService:
    def executar(self, *, banco, dados, itens):
        if not itens:
            raise ValueError("Itens do pedido são obrigatórios.")

        with transaction.atomic(using=banco):
            parametros = (dados or {}).get("parametros") or {}
            pedido = self._criar_pedido(
                banco=banco,
                dados=dados,
            )

            total = self._criar_itens(
                banco=banco,
                pedido=pedido,
                itens=itens,
            )

            desconto = parse_decimal(getattr(pedido, "pedi_desc", 0))
            frete = parse_decimal(getattr(pedido, "pedi_fret", 0))
            total_liquido_sem_credito = total - desconto + frete

            usar_credito = parametros.get("usar_credito")
            if usar_credito in (None, ""):
                usar_credito = parse_decimal(getattr(pedido, "pedi_cred", 0)) > 0

            credito_desejado = parametros.get("valor_credito")
            if credito_desejado in (None, ""):
                credito_desejado = getattr(pedido, "pedi_cred", None)

            credito_aplicado = Decimal("0.00")
            if usar_credito and getattr(pedido, "pedi_clie", None):
                credito_aplicado = CreditoTrocaPisosService.calcular_credito_aplicado(
                    banco=banco,
                    empresa=pedido.pedi_empr,
                    filial=pedido.pedi_fili,
                    cliente_id=pedido.pedi_clie,
                    total_liquido_sem_credito=total_liquido_sem_credito,
                    valor_desejado=credito_desejado,
                    excluir_pedido=pedido.pedi_nume,
                )

            pedido.pedi_cred = credito_aplicado
            pedido.pedi_tota = arredondar(total_liquido_sem_credito - credito_aplicado)
            Pedidospisos.objects.using(banco).filter(
                pedi_empr=pedido.pedi_empr,
                pedi_fili=pedido.pedi_fili,
                pedi_nume=pedido.pedi_nume,
            ).update(
                pedi_tota=pedido.pedi_tota,
                pedi_cred=pedido.pedi_cred,
            )

            self.gerar_titulos_receber(banco=banco, pedido=pedido, parametros=parametros)

            return pedido

    @staticmethod
    def _map_forma_recebimento(forma) -> str | None:
        if forma in (None, "", 99, "99"):
            return None
        try:
            v = int(forma)
        except (TypeError, ValueError):
            return None
        if v < 0:
            return None
        return f"{v:02d}" if v < 10 else str(v)

    @staticmethod
    def gerar_titulos_receber(*, banco: str, pedido: Pedidospisos, parametros: dict | None) -> None:
        parametros = parametros or {}
        financeiro = parametros.get("financeiro") or {}

        try:
            parcelas = int(financeiro.get("parcelas") or 1)
        except (TypeError, ValueError):
            parcelas = 1
        parcelas = max(parcelas, 1)

        condicao = str(financeiro.get("condicao") or "").strip()
        dias = []
        if condicao:
            for item in condicao.split():
                try:
                    dias.append(int(item))
                except (TypeError, ValueError):
                    continue

        entrada = parse_decimal(financeiro.get("entrada") or 0)
        if parcelas <= 1 and not dias and entrada <= 0:
            return

        if not getattr(pedido, "pedi_clie", None):
            raise ValidationError({"pedi_clie": ["Cliente obrigatório para gerar títulos."]})

        forma = PedidoCriarService._map_forma_recebimento(getattr(pedido, "pedi_form_paga", None))
        if not forma:
            return

        base = getattr(pedido, "pedi_data", None) or date.today()
        total = arredondar(getattr(pedido, "pedi_tota", 0), 2)
        entrada = arredondar(entrada, 2)
        restante = total - entrada
        if restante < 0:
            restante = Decimal("0.00")

        if restante <= 0:
            return

        valor_base = (restante / Decimal(parcelas)).quantize(Decimal("0.01"))
        diferenca = restante - (valor_base * Decimal(parcelas))

        doc = str(getattr(pedido, "pedi_nume", "") or "").strip()[:13]
        if not doc:
            return

        for idx in range(parcelas):
            parcela = str(idx + 1)
            valor = valor_base + (diferenca if idx == 0 else Decimal("0.00"))
            if valor <= 0:
                continue

            delta_dias = dias[idx] if idx < len(dias) else (30 * idx)
            venc = base + timedelta(days=int(delta_dias or 0))

            filtro_base = {
                "titu_empr": int(getattr(pedido, "pedi_empr")),
                "titu_fili": int(getattr(pedido, "pedi_fili")),
                "titu_clie": int(getattr(pedido, "pedi_clie")),
                "titu_titu": doc,
                "titu_parc": parcela,
            }

            filtro_pvp = {**filtro_base, "titu_seri": "PVP"}
            filtro_legado = {**filtro_base, "titu_seri": "PIS"}

            existente = Titulosreceber.objects.using(banco).filter(**filtro_pvp).first()
            if not existente:
                existente = Titulosreceber.objects.using(banco).filter(**filtro_legado).first()

            if existente:
                if (existente.titu_aber or "A") == "A":
                    Titulosreceber.objects.using(banco).filter(
                        **{
                            **filtro_base,
                            "titu_seri": str(getattr(existente, "titu_seri", "") or ""),
                        }
                    ).update(
                        titu_seri="PVP",
                        titu_emis=base,
                        titu_venc=venc,
                        titu_valo=valor,
                        titu_form_reci=forma,
                        titu_hist=f"Pedido Pisos {doc}",
                        titu_port=0,
                        titu_situ=0,
                        titu_vend=int(getattr(pedido, "pedi_vend", 0) or 0),
                        titu_tipo="Receber",
                        titu_prov=True,
                    )
                continue

            criar_titulo_receber(
                banco=banco,
                empresa_id=int(getattr(pedido, "pedi_empr")),
                filial_id=int(getattr(pedido, "pedi_fili")),
                dados={
                    **filtro_pvp,
                    "titu_emis": base,
                    "titu_venc": venc,
                    "titu_valo": valor,
                    "titu_form_reci": forma,
                    "titu_hist": f"Pedido Pisos {doc}",
                    "titu_port": 0,
                    "titu_situ": 0,
                    "titu_vend": int(getattr(pedido, "pedi_vend", 0) or 0),
                    "titu_tipo": "Receber",
                    "titu_prov": True,
                },
            )

    def _criar_pedido(self, *, banco, dados):
        ultimo = (
            Pedidospisos.objects.using(banco)
            .filter(
                pedi_empr=dados["pedi_empr"],
                pedi_fili=dados["pedi_fili"],
            )
            .order_by("-pedi_nume")
            .first()
        )

        proximo_numero = (ultimo.pedi_nume + 1) if ultimo else 1

        dados_pedido = dict(dados)
        dados_pedido.pop("itens_input", None)
        dados_pedido.pop("itens", None)
        dados_pedido.pop("parametros", None)
        dados_pedido.pop("usar_credito", None)
        dados_pedido.pop("valor_credito", None)

        dados_pedido["pedi_nume"] = proximo_numero
        dados_pedido["pedi_tota"] = Decimal("0.00")

        pedido = Pedidospisos.objects.using(banco).create(**dados_pedido)

        ClienteEnderecoService.preencher_pedido(
            banco=banco,
            pedido=pedido,
        )

        update_data = {}
        for campo in (
            "pedi_ende",
            "pedi_nume_ende",
            "pedi_cida",
            "pedi_esta",
            "pedi_comp",
            "pedi_bair",
            "pedi_comp_fone",
        ):
            if hasattr(pedido, campo):
                update_data[campo] = getattr(pedido, campo)
        if update_data:
            Pedidospisos.objects.using(banco).filter(
                pedi_empr=pedido.pedi_empr,
                pedi_fili=pedido.pedi_fili,
                pedi_nume=pedido.pedi_nume,
            ).update(**update_data)

        return pedido

    def _criar_itens(self, *, banco, pedido, itens):
        total = Decimal("0.00")
        campos_permitidos = {field.name for field in Itenspedidospisos._meta.fields}

        for idx, item in enumerate(itens, start=1):
            dados_item = self._normalizar_item(item, banco=banco, empresa=pedido.pedi_empr)

            dados_item = {
                chave: valor
                for chave, valor in dados_item.items()
                if chave in campos_permitidos
            }

            quantidade = parse_decimal(dados_item.get("item_quan"))
            valor_unitario = parse_decimal(dados_item.get("item_unit"))
            subtotal = arredondar(quantidade * valor_unitario)

            item_ambi = dados_item.get("item_ambi")
            if item_ambi in (None, "", 0, "0"):
                item_ambi = idx

            Itenspedidospisos.objects.using(banco).create(
                item_empr=pedido.pedi_empr,
                item_fili=pedido.pedi_fili,
                item_pedi=pedido.pedi_nume,
                item_nume=idx,
                item_ambi=item_ambi,
                item_suto=subtotal,
                **{
                    chave: valor
                    for chave, valor in dados_item.items()
                    if chave not in {
                        "item_empr",
                        "item_fili",
                        "item_pedi",
                        "item_nume",
                        "item_ambi",
                        "item_suto",
                    }
                },
            )

            total += subtotal

        return total

    def _normalizar_item(self, item, *, banco, empresa):
        dados = dict(item)

        mapa = {
            "area_m2": "item_m2",
            "observacoes": "item_obse",
            "produto_nome": "item_prod_nome",
            "item_nome": "item_nome_ambi",
            "quebra": "item_queb",
        }

        for origem, destino in mapa.items():
            if origem in dados:
                dados[destino] = dados.pop(origem)

        dados_calc = dados.pop("dados_calculo", None) or {}

        if dados_calc:
            if not dados.get("item_caix"):
                dados["item_caix"] = dados_calc.get("caixas_necessarias")

            if not dados.get("item_quan"):
                caixas = parse_decimal(dados.get("item_caix"))
                pc_por_caixa = parse_decimal(dados_calc.get("pc_por_caixa"))
                m2_por_caixa = parse_decimal(dados_calc.get("m2_por_caixa"))

                if pc_por_caixa > 0:
                    dados["item_quan"] = pc_por_caixa * caixas
                elif m2_por_caixa > 0:
                    dados["item_quan"] = m2_por_caixa * caixas

        self._completar_medidas_item(dados, banco=banco, empresa=empresa)

        dados["item_m2"] = parse_decimal(dados.get("item_m2"))
        dados["item_quan"] = parse_decimal(dados.get("item_quan"))
        dados["item_unit"] = parse_decimal(dados.get("item_unit"))
        dados["item_desc"] = parse_decimal(dados.get("item_desc"))
        dados["item_queb"] = parse_decimal(dados.get("item_queb"))

        return dados

    def _completar_medidas_item(self, dados: dict, *, banco, empresa) -> None:
        """Permite inserção manual por caixas/quantidade quando m² não for informado."""
        produto_id = (dados.get("item_prod") or "").strip()
        if not produto_id:
            return

        quantidade = parse_decimal(dados.get("item_quan"))
        caixas = parse_decimal(dados.get("item_caix"))
        metragem = parse_decimal(dados.get("item_m2"))

        if quantidade > 0 and caixas > 0 and metragem > 0:
            return

        produto = Produtos.objects.using(banco).filter(prod_codi=produto_id, prod_empr=str(empresa)).first()
        if not produto:
            return

        m2_por_caixa = parse_decimal(getattr(produto, "prod_cera_m2cx", 0))
        pc_por_caixa = parse_decimal(getattr(produto, "prod_cera_pccx", 0))

        if caixas <= 0 and quantidade > 0 and pc_por_caixa > 0:
            caixas = quantidade / pc_por_caixa

        if quantidade <= 0 and caixas > 0:
            if pc_por_caixa > 0:
                quantidade = caixas * pc_por_caixa
            elif m2_por_caixa > 0:
                quantidade = caixas * m2_por_caixa

        if metragem <= 0:
            if caixas > 0 and m2_por_caixa > 0:
                metragem = caixas * m2_por_caixa
            elif quantidade > 0 and pc_por_caixa > 0 and m2_por_caixa > 0:
                metragem = (quantidade / pc_por_caixa) * m2_por_caixa

        dados["item_caix"] = caixas
        dados["item_quan"] = quantidade
        dados["item_m2"] = metragem
