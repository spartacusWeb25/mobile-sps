from .utils_service import DadosEntidadesService
from .calculo_services import recomputar_total_pedido
from ..models import Itenspedidospisos

class PedidoService:
    @staticmethod
    def preparar_pedido(pedido, request):
        """
        Preenche dados do cliente e recalcula totais do pedido.
        """
        banco = pedido._state.db or 'default'

        DadosEntidadesService.preencher_dados_do_cliente(pedido, request)

        itens = Itenspedidospisos.objects.using(banco).filter(
            item_empr=pedido.pedi_empr,
            item_fili=pedido.pedi_fili,
            item_pedi=pedido.pedi_nume
        )

        if not itens.exists():
            pedido.pedi_tota = 0
            return pedido

        pedido.pedi_tota = recomputar_total_pedido(banco, pedido)
        return pedido
