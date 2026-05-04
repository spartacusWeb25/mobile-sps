from Entidades.models import Entidades

from Pisos.models import Itensorcapisos


class OrcamentoPisosImpressaoService:
    @staticmethod
    def obter_contexto(*, banco, orcamento):
        cliente = Entidades.objects.using(banco).filter(enti_clie=orcamento.orca_clie).first()
        vendedor = Entidades.objects.using(banco).filter(enti_clie=orcamento.orca_vend).first()

        itens = Itensorcapisos.objects.using(banco).filter(
            item_empr=orcamento.orca_empr,
            item_fili=orcamento.orca_fili,
            item_orca=orcamento.orca_nume,
        ).order_by("item_nume", "item_ambi")

        return {
            "cliente": cliente,
            "vendedor": vendedor,
            "itens": itens,
        }
