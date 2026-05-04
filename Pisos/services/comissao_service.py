# Pisos/services/comissao_service.py

from decimal import Decimal, ROUND_HALF_UP

from Entidades.models import Entidades
from Produtos.models import Produtos, GrupoProduto
from Pisos.models import Pedidospisos, Itenspedidospisos


class ComissaoService:

    @staticmethod
    def decimal(valor):
        if valor is None:
            return Decimal("0.00")

        return Decimal(str(valor)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    @classmethod
    def listar_vendedores(cls, *, db_alias, empresa_id=None):
        qs = (
            Entidades.objects
            .using(db_alias)
            .filter(enti_tipo_enti="VE")
        )
        if empresa_id not in [None, ""]:
            qs = qs.filter(enti_empr=empresa_id)
        return qs.order_by("enti_nome")

    @classmethod
    def listar_grupos_comissionados(cls, *, db_alias):
        return (
            GrupoProduto.objects
            .using(db_alias)
            .filter(grup_comi_vend__gt=0)
            .order_by("descricao")
        )

    @classmethod
    def calcular_comissoes(
        cls,
        *,
        db_alias,
        empresa_id=None,
        filial_id=None,
        data_inicial=None,
        data_final=None,
        vendedor_codigo=None,
        grupo_codigo=None,
        status=None,
        agrupar_por="vendedor",
        vendedores=None,
    ):
        data_minima = "2000-01-01"
        if not data_inicial or str(data_inicial) < data_minima:
            data_inicial = data_minima

        vendedores_lista = list(vendedores) if vendedores is not None else None
        vendedor_codigos = None
        if vendedor_codigo not in [None, ""] and vendedores_lista is not None:
            vendedor_sel = next(
                (v for v in vendedores_lista if str(getattr(v, "enti_clie", "")) == str(vendedor_codigo)),
                None,
            )
            if vendedor_sel is not None:
                cpfcnpj = getattr(vendedor_sel, "enti_cpfcnpj", None)
                nome = (getattr(vendedor_sel, "enti_nome", "") or "").strip().lower()
                if cpfcnpj:
                    vendedor_codigos = {
                        getattr(v, "enti_clie")
                        for v in vendedores_lista
                        if getattr(v, "enti_cpfcnpj", None) == cpfcnpj
                    }
                elif nome:
                    vendedor_codigos = {
                        getattr(v, "enti_clie")
                        for v in vendedores_lista
                        if (getattr(v, "enti_nome", "") or "").strip().lower() == nome
                    }

        pedidos = (
            Pedidospisos.objects
            .using(db_alias)
            .only(
                "pedi_empr",
                "pedi_fili",
                "pedi_nume",
                "pedi_data",
                "pedi_vend",
                "pedi_stat",
                "pedi_tota",
            )
        )

        if empresa_id not in [None, ""]:
            pedidos = pedidos.filter(pedi_empr=empresa_id)

        if filial_id not in [None, ""]:
            pedidos = pedidos.filter(pedi_fili=filial_id)

        if data_inicial:
            pedidos = pedidos.filter(pedi_data__gte=data_inicial)

        if data_final:
            pedidos = pedidos.filter(pedi_data__lte=data_final)

        if vendedor_codigo:
            if vendedor_codigos:
                pedidos = pedidos.filter(pedi_vend__in=list(vendedor_codigos))
            else:
                pedidos = pedidos.filter(pedi_vend=vendedor_codigo)

        if status not in [None, ""]:
            pedidos = pedidos.filter(pedi_stat=status)

        pedidos_list = list(pedidos)
        pedidos_map = {
            (pedido.pedi_empr, pedido.pedi_fili, pedido.pedi_nume): pedido
            for pedido in pedidos_list
        }

        if not pedidos_map:
            return []

        pedidos_emprs = {p.pedi_empr for p in pedidos_list}
        pedidos_filis = {p.pedi_fili for p in pedidos_list}
        pedidos_numes = {p.pedi_nume for p in pedidos_list}

        itens = (
            Itenspedidospisos.objects
            .using(db_alias)
            .filter(item_pedi__in=list(pedidos_numes))
            .only("item_empr", "item_fili", "item_pedi", "item_prod", "item_prod_nome", "item_quan", "item_unit", "item_suto")
        )

        if empresa_id not in [None, ""]:
            itens = itens.filter(item_empr=empresa_id)
        elif pedidos_emprs:
            itens = itens.filter(item_empr__in=list(pedidos_emprs))

        if filial_id not in [None, ""]:
            itens = itens.filter(item_fili=filial_id)
        elif pedidos_filis:
            itens = itens.filter(item_fili__in=list(pedidos_filis))

        codigos_produtos = {str(i.item_prod) for i in itens if getattr(i, "item_prod", None) is not None}
        empresas_itens = {str(i.item_empr) for i in itens if getattr(i, "item_empr", None) is not None}
        produtos_map = {
            (str(getattr(prod, "prod_empr", "")), str(prod.prod_codi)): prod
            for prod in (
                Produtos.objects.using(db_alias)
                .filter(prod_codi__in=list(codigos_produtos))
                .filter(prod_empr__in=list(empresas_itens) if empresas_itens else [])
                .select_related("prod_grup", "prod_marc")
                .only(
                    "prod_empr",
                    "prod_codi",
                    "prod_nome",
                    "prod_grup",
                    "prod_grup__codigo",
                    "prod_grup__descricao",
                    "prod_grup__grup_comi_vend",
                    "prod_marc",
                    "prod_marc__codigo",
                    "prod_marc__nome",
                    "prod_marc__comissao",
                )
            )
        }

        vendedores_map = {
            str(vendedor.enti_clie): vendedor
            for vendedor in (vendedores_lista if vendedores_lista is not None else cls.listar_vendedores(db_alias=db_alias, empresa_id=empresa_id))
        }

        resultado = {}

        agrupar_por = (agrupar_por or "vendedor").strip().lower()
        if agrupar_por not in {"vendedor", "grupo", "produto", "pedido", "data"}:
            agrupar_por = "vendedor"

        for item in itens:
            pedido = pedidos_map.get((item.item_empr, item.item_fili, item.item_pedi))

            if not pedido:
                continue

            vendedor = vendedores_map.get(str(pedido.pedi_vend))

            if not vendedor:
                continue

            produto = produtos_map.get((str(item.item_empr), str(item.item_prod)))
            produto_nome = getattr(produto, "prod_nome", None) or getattr(item, "item_prod_nome", None) or str(getattr(item, "item_prod", "") or "")
            grupo = getattr(produto, "prod_grup", None) if produto is not None else None
            marca = getattr(produto, "prod_marc", None) if produto is not None else None

            if grupo_codigo and str(getattr(grupo, "codigo", "")) != str(grupo_codigo):
                continue

            percentual_grupo = cls.decimal(getattr(grupo, "grup_comi_vend", 0))
            percentual_marca = cls.decimal(getattr(marca, "comissao", 0)) if marca is not None else Decimal("0.00")

            if percentual_marca > 0:
                comissao_origem = "marca"
                comissao_origem_codigo = getattr(marca, "codigo", None)
                comissao_origem_nome = getattr(marca, "nome", None)
                percentual = percentual_marca
            else:
                comissao_origem = "grupo"
                comissao_origem_codigo = getattr(grupo, "codigo", None)
                comissao_origem_nome = getattr(grupo, "descricao", None)
                percentual = percentual_grupo

            total_item = cls.decimal(item.item_suto)

            if total_item <= 0:
                quantidade = cls.decimal(item.item_quan)
                valor_unitario = cls.decimal(item.item_unit)
                total_item = quantidade * valor_unitario

            valor_comissao = (
                total_item * percentual / Decimal("100")
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            grupo_codigo_atual = str(getattr(grupo, "codigo", "") or "")
            origem_codigo_atual = str(comissao_origem_codigo or "")
            origem_chave = f"{comissao_origem[:1]}_{origem_codigo_atual}"
            if agrupar_por == "vendedor":
                agrupamento = vendedor.enti_nome
                chave = f"v_{vendedor.enti_clie}_{origem_chave}"
            elif agrupar_por == "grupo":
                agrupamento = getattr(grupo, "descricao", "") or str(getattr(grupo, "codigo", ""))
                chave = f"g_{getattr(grupo, 'codigo', '')}_{origem_chave}"
            elif agrupar_por == "produto":
                agrupamento = produto_nome
                chave = f"p_{str(getattr(item, 'item_empr', '') or '')}_{str(getattr(item, 'item_prod', '') or '')}_{origem_chave}"
            elif agrupar_por == "pedido":
                agrupamento = str(pedido.pedi_nume)
                chave = f"o_{pedido.pedi_nume}_{origem_chave}"
            else:
                agrupamento = pedido.pedi_data.isoformat() if getattr(pedido, "pedi_data", None) else ""
                chave = f"d_{agrupamento}_{origem_chave}"

            if chave not in resultado:
                resultado[chave] = {
                    "agrupamento": agrupamento,
                    "percentual": percentual,
                    "comissao_origem": comissao_origem,
                    "comissao_origem_codigo": comissao_origem_codigo,
                    "comissao_origem_nome": comissao_origem_nome,
                    "total_vendido": Decimal("0.00"),
                    "valor_comissao": Decimal("0.00"),
                    "quantidade_itens": 0,
                    "pedidos": set(),
                    "vendedores": set(),
                    "grupos": set(),
                    "marcas": set(),
                    "produtos": set(),
                    "datas": set(),
                }

            resultado[chave]["total_vendido"] += total_item
            resultado[chave]["valor_comissao"] += valor_comissao
            resultado[chave]["quantidade_itens"] += 1
            resultado[chave]["pedidos"].add(pedido.pedi_nume)
            resultado[chave]["vendedores"].add((vendedor.enti_clie, vendedor.enti_nome))
            resultado[chave]["grupos"].add((getattr(grupo, "codigo", None), getattr(grupo, "descricao", None)))
            resultado[chave]["marcas"].add((getattr(marca, "codigo", None), getattr(marca, "nome", None)))
            resultado[chave]["produtos"].add((getattr(item, "item_prod", None), produto_nome))
            if getattr(pedido, "pedi_data", None):
                resultado[chave]["datas"].add(pedido.pedi_data)

        dados = []

        for item in resultado.values():
            item["quantidade_pedidos"] = len(item["pedidos"])

            if len(item["vendedores"]) == 1:
                v_cod, v_nome = next(iter(item["vendedores"]))
                item["vendedor_codigo"] = v_cod
                item["vendedor_nome"] = v_nome
            else:
                item["vendedor_codigo"] = None
                item["vendedor_nome"] = None

            if len(item["grupos"]) == 1:
                g_cod, g_desc = next(iter(item["grupos"]))
                item["grupo_codigo"] = g_cod
                item["grupo_descricao"] = g_desc
            else:
                item["grupo_codigo"] = None
                item["grupo_descricao"] = None

            if len(item["marcas"]) == 1:
                m_cod, m_nome = next(iter(item["marcas"]))
                item["marca_codigo"] = m_cod
                item["marca_nome"] = m_nome
            else:
                item["marca_codigo"] = None
                item["marca_nome"] = None

            if len(item["produtos"]) == 1:
                p_cod, p_nome = next(iter(item["produtos"]))
                item["produto_codigo"] = p_cod
                item["produto_nome"] = p_nome
            else:
                item["produto_codigo"] = None
                item["produto_nome"] = None

            if len(item["pedidos"]) == 1:
                item["pedido_numero"] = next(iter(item["pedidos"]))
            else:
                item["pedido_numero"] = None

            if len(item["datas"]) == 1:
                item["data"] = next(iter(item["datas"]))
            else:
                item["data"] = None

            del item["pedidos"]
            del item["vendedores"]
            del item["grupos"]
            del item["marcas"]
            del item["produtos"]
            del item["datas"]
            dados.append(item)

        return sorted(
            dados,
            key=lambda x: (str(x.get("agrupamento") or ""), str(x.get("vendedor_nome") or ""), str(x.get("grupo_descricao") or ""))
        )
