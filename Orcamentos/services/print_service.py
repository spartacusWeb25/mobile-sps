import base64

from Entidades.models import Entidades
from Licencas.models import Empresas, Filiais
from Produtos.models import Produtos

from Orcamentos.models import ItensOrcamento


class OrcamentoPrintService:
    @staticmethod
    def montar_contexto(*, banco, orcamento):
        contexto = {}

        empresa = Empresas.objects.using(banco).filter(empr_codi=orcamento.pedi_empr).first()
        filial = Filiais.objects.using(banco).filter(
            empr_empr=orcamento.pedi_empr,
            empr_codi=orcamento.pedi_fili,
        ).first()

        contexto["empresa"] = empresa
        contexto["filial"] = filial

        if filial and filial.empr_logo:
            logo_data = filial.empr_logo
            if isinstance(logo_data, memoryview):
                logo_data = logo_data.tobytes()
            if isinstance(logo_data, bytes):
                contexto["logo_b64"] = base64.b64encode(logo_data).decode("utf-8")

        contexto["cliente"] = Entidades.objects.using(banco).filter(
            enti_empr=orcamento.pedi_empr,
            enti_clie=orcamento.pedi_forn,
        ).first()

        contexto["vendedor"] = Entidades.objects.using(banco).filter(
            enti_empr=orcamento.pedi_empr,
            enti_clie=orcamento.pedi_vend,
        ).first()

        itens_qs = ItensOrcamento.objects.using(banco).filter(
            iped_empr=orcamento.pedi_empr,
            iped_fili=orcamento.pedi_fili,
            iped_pedi=str(orcamento.pedi_nume),
        ).order_by("iped_item")

        codigos = [i.iped_prod for i in itens_qs]
        produtos = Produtos.objects.using(banco).filter(
            prod_codi__in=codigos,
            prod_empr=str(orcamento.pedi_empr),
        )
        prod_map = {
            p.prod_codi: {
                "nome": p.prod_nome,
                "unidade": p.prod_unme_id,
                "has_foto": bool(p.prod_foto),
            }
            for p in produtos
        }

        itens_detalhados = []
        for i in itens_qs:
            meta = prod_map.get(i.iped_prod, {})
            itens_detalhados.append(
                {
                    "prod_codigo": i.iped_prod,
                    "prod_nome": meta.get("nome") or i.iped_prod,
                    "prod_unidade": meta.get("unidade") or getattr(i, "iped_unme", None),
                    "has_foto": bool(meta.get("has_foto")),
                    "iped_quan": i.iped_quan,
                    "iped_unit": i.iped_unit,
                    "iped_tota": i.iped_tota,
                    "iped_desc": i.iped_desc,
                    "iped_item": getattr(i, "iped_item", None),
                }
            )
        contexto["itens_detalhados"] = itens_detalhados

        return contexto
