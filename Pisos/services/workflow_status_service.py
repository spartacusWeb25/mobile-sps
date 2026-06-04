
from django.core.exceptions import ValidationError
from Pisos.models import StatusPisos, Pedidospisos, Orcamentopisos

class WorkflowStatusPisosService:

    @staticmethod
    def alterar_status_pedido(banco, empresa, filial, numero, novo_codigo):
        status = StatusPisos.objects.using(banco).filter(
            stat_empr=empresa,
            stat_fili=filial,
            stat_tipo=StatusPisos.TIPO_PEDIDO,
            stat_codigo=novo_codigo,
            stat_ativo=True,
        ).first()

        if not status:
            raise ValidationError("Status de pedido inválido.")

        pedido = Pedidospisos.objects.using(banco).get(
            pedi_empr=empresa,
            pedi_fili=filial,
            pedi_nume=numero,
        )

        pedido.pedi_stat = status.stat_codigo
        Pedidospisos.objects.using(banco).filter(
            pedi_empr=empresa,
            pedi_fili=filial,
            pedi_nume=numero,
        ).update(pedi_stat=status.stat_codigo)

        return pedido, status

    @staticmethod
    def alterar_status_orcamento(banco, empresa, filial, numero, novo_codigo):
        status = StatusPisos.objects.using(banco).filter(
            stat_empr=empresa,
            stat_fili=filial,
            stat_tipo=StatusPisos.TIPO_ORCAMENTO,
            stat_codigo=novo_codigo,
            stat_ativo=True,
        ).first()

        if not status:
            raise ValidationError("Status de orçamento inválido.")

        orcamento = Orcamentopisos.objects.using(banco).get(
            orca_empr=empresa,
            orca_fili=filial,
            orca_nume=numero,
        )

        orcamento.orca_stat = status.stat_codigo
        Orcamentopisos.objects.using(banco).filter(
            orca_empr=empresa,
            orca_fili=filial,
            orca_nume=numero,
        ).update(orca_stat=status.stat_codigo)

        return orcamento, status
