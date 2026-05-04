import json
from decimal import Decimal

from django.views.generic import TemplateView
from core.utils import get_db_from_slug

from Pisos.services.comissao_service import ComissaoService


class ComissaoVendedorView(TemplateView):
    template_name = "Pisos/comissoes_vendedores.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        slug = self.kwargs["slug"]
        db_alias = get_db_from_slug(slug)

        empresa_param = self.request.GET.get("empresa")
        filial_param = self.request.GET.get("filial")

        sess_empresa = (
            self.request.session.get("empresa_id")
            or self.request.session.get("empresa")
            or self.request.session.get("empr_codi")
        )
        sess_filial = (
            self.request.session.get("filial_id")
            or self.request.session.get("filial")
            or self.request.session.get("fili_codi")
        )

        empresa_id = sess_empresa if empresa_param in [None, ""] else empresa_param
        filial_id = sess_filial if filial_param in [None, ""] else filial_param

        try:
            empresa_id = int(empresa_id) if empresa_id not in [None, "", "all"] else None
        except Exception:
            empresa_id = None

        try:
            filial_id = int(filial_id) if filial_id not in [None, "", "all"] else None
        except Exception:
            filial_id = None

        data_inicial = self.request.GET.get("data_inicial")
        data_final = self.request.GET.get("data_final")
        vendedor = self.request.GET.get("vendedor")
        grupo = self.request.GET.get("grupo")
        agrupar_por = self.request.GET.get("agrupar_por") or "vendedor"
        status = self.request.GET.get("status")

        context["slug"] = slug

        vendedores = list(
            ComissaoService.listar_vendedores(
                db_alias=db_alias,
                empresa_id=empresa_id,
            )
        )
        context["vendedores"] = vendedores

        context["grupos"] = ComissaoService.listar_grupos_comissionados(
            db_alias=db_alias
        )

        try:
            from Licencas.models import Empresas, Filiais

            context["empresas_list"] = list(
                Empresas.objects.using(db_alias).only("empr_codi", "empr_nome").order_by("empr_nome")
            )

            filiais_qs = Filiais.objects.using(db_alias).only("empr_empr", "empr_codi", "empr_nome").order_by("empr_nome")
            if empresa_id is not None:
                filiais_qs = filiais_qs.filter(empr_codi=empresa_id)
            context["filiais_list"] = list(filiais_qs)
        except Exception:
            context["empresas_list"] = []
            context["filiais_list"] = []

        comissoes = ComissaoService.calcular_comissoes(
            db_alias=db_alias,
            empresa_id=empresa_id,
            filial_id=filial_id,
            data_inicial=data_inicial,
            data_final=data_final,
            vendedor_codigo=vendedor,
            grupo_codigo=grupo,
            agrupar_por=agrupar_por,
            status=status,
            vendedores=vendedores,
        )
        context["comissoes"] = comissoes

        context["filtros"] = {
            "empresa": "all" if empresa_param == "all" else (str(empresa_id) if empresa_id is not None else ""),
            "filial": "all" if filial_param == "all" else (str(filial_id) if filial_id is not None else ""),
            "data_inicial": data_inicial,
            "data_final": data_final,
            "vendedor": vendedor,
            "grupo": grupo,
            "agrupar_por": agrupar_por,
            "status": status,
        }

        total_vendido = sum((c.get("total_vendido") or 0) for c in comissoes) if comissoes else Decimal("0.00")
        total_comissao = sum((c.get("valor_comissao") or 0) for c in comissoes) if comissoes else Decimal("0.00")
        quantidade_pedidos = sum((c.get("quantidade_pedidos") or 0) for c in comissoes)
        quantidade_itens = sum((c.get("quantidade_itens") or 0) for c in comissoes)

        context["metricas"] = {
            "total_vendido": total_vendido,
            "total_comissao": total_comissao,
            "quantidade_pedidos": quantidade_pedidos,
            "quantidade_itens": quantidade_itens,
        }

        labels = [str(c.get("agrupamento") or "-") for c in comissoes]
        comissoes_vals = [float(c.get("valor_comissao") or 0) for c in comissoes]
        vendas_vals = [float(c.get("total_vendido") or 0) for c in comissoes]

        labels_json = json.dumps(labels, ensure_ascii=False)
        comissoes_json = json.dumps(comissoes_vals)
        vendas_json = json.dumps(vendas_vals)

        context["chart"] = {
            "labels": labels_json,
            "comissoes": comissoes_json,
            "vendas": vendas_json,
        }

        return context
