from django.db import transaction
from Produtos.models import Produtos
from controledevisitas.models import  Controlevisita, ItensVisita
from Pisos.services.metragem_service import MetragemProdutoService


class ItemVisitaService:
        def __init__(self, *, banco, empresa_id=None, filial_id=None):
            self.banco = banco
            self.empresa_id = empresa_id
            self.filial_id = filial_id

        def buscar_visita(self, ctrl_id):
            return (
                Controlevisita.objects
                .using(self.banco)
                .select_related("ctrl_empresa")
                .get(ctrl_id=ctrl_id)
            )

        @transaction.atomic
        def criar_item_calculado(self, *, ctrl_id, dados):
            visita = self.buscar_visita(ctrl_id)

            produto_id = dados["produto_codigo"]
            metragem = dados.get("metragem") or dados.get("quantidade") or 0
            quebra = dados.get("percentual_quebra") or 0
            condicao = dados.get("condicao") or "0"
            empresa_id = self._get_empresa(visita)
            filial_id = self._get_filial(visita)

            calculo = MetragemProdutoService().executar(
                banco=self.banco,
                produto_id=produto_id,
                tamanho_m2=metragem,
                percentual_quebra=quebra,
                condicao=condicao,
                empresa_id=empresa_id,
                filial_id=filial_id,
            )

            item = ItensVisita.objects.using(self.banco).create(
                item_empr_id=empresa_id,
                item_fili=filial_id,
                item_visita=visita,

                item_prod=produto_id,
                item_desc_prod=calculo.get("produto_nome") or None,

                item_tipo_calculo="pisos",

                item_m2=metragem,
                item_queb=quebra,
                item_caix=calculo.get("caixas_necessarias"),

                item_quan=calculo.get("metragem_real") or metragem,
                item_unli=calculo.get("unidade_medida") or None,

                # preço calculado
                item_unit=calculo["preco_unitario"],

                item_obse=dados.get("observacoes") or None,
            )

            return item, calculo

        @transaction.atomic
        def atualizar_item_calculado(self, *, item, dados):
            produto_id = dados["produto_codigo"]
            metragem = dados.get("metragem") or dados.get("quantidade") or 0
            quebra = dados.get("percentual_quebra") or 0
            condicao = dados.get("condicao") or "0"
            empresa_id = getattr(item, "item_empr_id", None) or self.empresa_id
            filial_id = getattr(item, "item_fili", None) or self.filial_id

            calculo = MetragemProdutoService().executar(
                banco=self.banco,
                produto_id=produto_id,
                tamanho_m2=metragem,
                percentual_quebra=quebra,
                condicao=condicao,
                empresa_id=empresa_id,
                filial_id=filial_id,
            )

            item.item_prod = produto_id
            item.item_desc_prod = calculo.get("produto_nome") or item.item_desc_prod
            item.item_tipo_calculo = "pisos"
            item.item_m2 = metragem
            item.item_queb = quebra
            item.item_caix = calculo.get("caixas_necessarias")
            item.item_quan = calculo.get("metragem_real") or metragem
            item.item_unit = calculo["preco_unitario"]
            item.item_unli = calculo.get("unidade_medida") or item.item_unli
            item.item_obse = dados.get("observacoes") or None

            item.save(using=self.banco)

            return item, calculo

        def _get_empresa(self, visita):
            return (
                getattr(getattr(visita, "ctrl_empresa", None), "empr_codi", None)
                or self.empresa_id
                or 1
            )

        def _get_filial(self, visita):
            return (
                getattr(visita, "ctrl_filial", None)
                or self.filial_id
                or 1
            )
        
