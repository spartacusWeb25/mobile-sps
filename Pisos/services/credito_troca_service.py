from decimal import Decimal

from django.db.models import Sum

from Pisos.models import Pedidospisos, Orcamentopisos


class CreditoTrocaPisosService:
    @staticmethod
    def calcular_resumo(*, banco, empresa, filial, cliente_id, excluir_pedido=None, excluir_orcamento=None):
        try:
            from devolucoes_pisos.models import Creditotrocas
        except Exception:
            Creditotrocas = None

        total_creditos = Decimal("0.00")
        if Creditotrocas is not None:
            total_creditos = (
                Creditotrocas.objects.using(banco)
                .filter(
                    cred_fina_empr=empresa,
                    cred_fina_fili=filial,
                    cred_fina_clie=int(cliente_id),
                )
                .aggregate(v=Sum("cred_fina_valo"))
                .get("v")
                or Decimal("0.00")
            )

        qs_ped = Pedidospisos.objects.using(banco).filter(
            pedi_empr=empresa,
            pedi_fili=filial,
            pedi_clie=int(cliente_id),
        )
        if excluir_pedido is not None:
            qs_ped = qs_ped.exclude(pedi_nume=int(excluir_pedido))
        total_usado_ped = qs_ped.aggregate(v=Sum("pedi_cred")).get("v") or Decimal("0.00")

        qs_orc = Orcamentopisos.objects.using(banco).filter(
            orca_empr=empresa,
            orca_fili=filial,
            orca_clie=int(cliente_id),
        )
        if excluir_orcamento is not None:
            qs_orc = qs_orc.exclude(orca_nume=int(excluir_orcamento))
        total_usado_orc = qs_orc.aggregate(v=Sum("orca_cred")).get("v") or Decimal("0.00")

        disponivel = total_creditos - total_usado_ped - total_usado_orc
        if disponivel < 0:
            disponivel = Decimal("0.00")

        return {
            "total_creditos": Decimal(total_creditos or 0),
            "total_usado_pedidos": Decimal(total_usado_ped or 0),
            "total_usado_orcamentos": Decimal(total_usado_orc or 0),
            "total_disponivel": Decimal(disponivel or 0),
        }

    @staticmethod
    def calcular_credito_aplicado(*, banco, empresa, filial, cliente_id, total_liquido_sem_credito, valor_desejado=None, excluir_pedido=None, excluir_orcamento=None):
        total_liq = Decimal(total_liquido_sem_credito or 0)
        if total_liq <= 0:
            return Decimal("0.00")

        resumo = CreditoTrocaPisosService.calcular_resumo(
            banco=banco,
            empresa=empresa,
            filial=filial,
            cliente_id=cliente_id,
            excluir_pedido=excluir_pedido,
            excluir_orcamento=excluir_orcamento,
        )
        disponivel = Decimal(resumo["total_disponivel"] or 0)
        if disponivel <= 0:
            return Decimal("0.00")

        if valor_desejado in (None, ""):
            desejado = disponivel
        else:
            try:
                desejado = Decimal(str(valor_desejado))
            except Exception:
                desejado = Decimal("0.00")

        if desejado < 0:
            desejado = Decimal("0.00")

        aplicado = min(disponivel, desejado, total_liq)
        if aplicado < 0:
            aplicado = Decimal("0.00")

        return aplicado

