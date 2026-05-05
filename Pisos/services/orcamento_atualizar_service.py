from decimal import Decimal
from django.db import transaction

from Pisos.models import Orcamentopisos, Itensorcapisos
from Pisos.services.orcamento_criar_service import OrcamentoCriarService
from Pisos.services.utils_service import parse_decimal, arredondar
from Pisos.services.credito_troca_service import CreditoTrocaPisosService


class OrcamentoAtualizarService:
    def executar(self, *, banco, orcamento, dados, itens):
        if not itens:
            raise ValueError("Itens do orçamento são obrigatórios.")

        with transaction.atomic(using=banco):
            parametros = (dados or {}).get("parametros") or {}
            dados_orcamento = dict(dados)
            dados_orcamento.pop("itens_input", None)
            dados_orcamento.pop("itens", None)
            dados_orcamento.pop("parametros", None)
            dados_orcamento.pop("usar_credito", None)
            dados_orcamento.pop("valor_credito", None)

            for campo, valor in dados_orcamento.items():
                setattr(orcamento, campo, valor)

            Itensorcapisos.objects.using(banco).filter(
                item_empr=orcamento.orca_empr,
                item_fili=orcamento.orca_fili,
                item_orca=orcamento.orca_nume,
            ).delete()

            total = OrcamentoCriarService()._criar_itens(
                banco=banco,
                orcamento=orcamento,
                itens=itens,
            )

            desconto = parse_decimal(getattr(orcamento, "orca_desc", 0))
            frete = parse_decimal(getattr(orcamento, "orca_fret", 0))

            total_liquido_sem_credito = total - desconto + frete

            usar_credito = parametros.get("usar_credito")
            if usar_credito in (None, ""):
                usar_credito = parse_decimal(getattr(orcamento, "orca_cred", 0)) > 0

            credito_desejado = parametros.get("valor_credito")
            if credito_desejado in (None, ""):
                credito_desejado = getattr(orcamento, "orca_cred", None)

            credito_aplicado = Decimal("0.00")
            if usar_credito and getattr(orcamento, "orca_clie", None):
                credito_aplicado = CreditoTrocaPisosService.calcular_credito_aplicado(
                    banco=banco,
                    empresa=orcamento.orca_empr,
                    filial=orcamento.orca_fili,
                    cliente_id=orcamento.orca_clie,
                    total_liquido_sem_credito=total_liquido_sem_credito,
                    valor_desejado=credito_desejado,
                    excluir_orcamento=orcamento.orca_nume,
                )

            orcamento.orca_cred = credito_aplicado
            orcamento.orca_tota = arredondar(total_liquido_sem_credito - credito_aplicado)
            orcamento.save(using=banco)

            return orcamento
