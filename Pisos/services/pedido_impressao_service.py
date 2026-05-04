from Entidades.models import Entidades

from Pisos.models import Itenspedidospisos


class PedidoPisosImpressaoService:
    @staticmethod
    def obter_contexto(*, banco, pedido):
        cliente = Entidades.objects.using(banco).filter(enti_clie=pedido.pedi_clie).first()
        vendedor = Entidades.objects.using(banco).filter(enti_clie=pedido.pedi_vend).first()

        itens = Itenspedidospisos.objects.using(banco).filter(
            item_empr=pedido.pedi_empr,
            item_fili=pedido.pedi_fili,
            item_pedi=pedido.pedi_nume,
        ).order_by("item_nume", "item_ambi")

        return {
            "cliente": cliente,
            "vendedor": vendedor,
            "itens": itens,
        }
