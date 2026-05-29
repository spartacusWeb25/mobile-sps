# services/painel_pedidos_service.py

from django.utils.timezone import now
from django.db.models import Q

from Pisos.models import Pedidospisos


class PainelPedidosService:

    @staticmethod
    def pedidos_pendentes_compra(empr, fili=None):
        """
        Pedido pendente de compra:
        - sem data de compra workflow
        - não cancelado
        """

        filtros = Q()
        if empr:
            filtros &= Q(pedi_empr=empr)
        filtros &= ~Q(pedi_stat=1)

        if fili:
            filtros &= Q(pedi_fili=fili)

        return (
            Pedidospisos.objects
            .filter(filtros)
            .filter(
                Q(pedi_data_comp_work__isnull=True)
            )
            .order_by('-pedi_nume')
            .values(
                'pedi_nume',
                'pedi_clie',
                'pedi_vend',
                'pedi_fech',
                'pedi_data_prev_entr',
                'pedi_desc_comp_work',
                'pedi_empr',
                'pedi_fili',
                'pedi_stat',
            )
        )

    @staticmethod
    def pedidos_prazo_entrega_expirado(empr, fili=None):

        hoje = now().date()

        filtros = Q()
        if empr:
            filtros &= Q(pedi_empr=empr)
        filtros &= Q(pedi_data_prev_entr__lt=hoje)
        filtros &= ~Q(pedi_stat=1)

        if fili:
            filtros &= Q(pedi_fili=fili)

        return (
            Pedidospisos.objects
            .filter(filtros)
            .order_by('pedi_data_prev_entr')
            .values(
                'pedi_nume',
                'pedi_clie',
                'pedi_vend',
                'pedi_data_prev_entr',
                'pedi_obse',
                'pedi_empr',
                'pedi_fili',
            )
        )