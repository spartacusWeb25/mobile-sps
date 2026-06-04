from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

try:
    from rest_framework.exceptions import ValidationError as DRFValidationError
except Exception:
    DRFValidationError = None

from Pisos.models import Pedidospisos, Itenspedidospisos
from Pisos.services.pedido_criar_service import PedidoCriarService
from Pisos.services.cliente_service import ClienteEnderecoService
from Pisos.services.utils_service import parse_decimal, arredondar
from Pisos.services.credito_troca_service import CreditoTrocaPisosService


class PedidoAtualizarService:
    def executar(self, *, banco, pedido, dados, itens):
        if not itens:
            raise ValueError("Itens do pedido são obrigatórios.")

        with transaction.atomic(using=banco):
            chave = (
                int(getattr(pedido, "pedi_empr")),
                int(getattr(pedido, "pedi_fili")),
                int(getattr(pedido, "pedi_nume")),
            )
            parametros = (dados or {}).get("parametros") or {}
            dados_pedido = dict(dados)
            chave_original_pedido = (
                pedido.pedi_empr,
                pedido.pedi_fili,
                pedido.pedi_nume,
            )

            dados_pedido.pop("itens_input", None)
            dados_pedido.pop("itens", None)
            dados_pedido.pop("parametros", None)
            dados_pedido.pop("usar_credito", None)
            dados_pedido.pop("valor_credito", None)
            dados_pedido.pop("pedi_empr", None)
            dados_pedido.pop("pedi_fili", None)
            dados_pedido.pop("pedi_nume", None)

            pedido = (
                Pedidospisos.objects.using(banco)
                .select_for_update()
                .get(pedi_empr=chave[0], pedi_fili=chave[1], pedi_nume=chave[2])
            )

            # Se o formulário não enviou explicitamente pedi_stat (campo vazio), não sobrescrever
            if 'pedi_stat' in dados_pedido and (dados_pedido.get('pedi_stat') is None or str(dados_pedido.get('pedi_stat')).strip() == ""):
                dados_pedido.pop('pedi_stat', None)

            for campo, valor in dados_pedido.items():
                setattr(pedido, campo, valor)

            ClienteEnderecoService.preencher_pedido(banco=banco, pedido=pedido)

            # Remove itens antigos
            Itenspedidospisos.objects.using(banco).filter(
                item_empr=chave_original_pedido[0],
                item_fili=chave_original_pedido[1],
                item_pedi=chave_original_pedido[2],
            ).delete()

            # Recria itens (reutiliza lógica do criar)
            total = PedidoCriarService()._criar_itens(
                banco=banco,
                pedido=pedido,
                itens=itens,
            )

            desconto = parse_decimal(getattr(pedido, "pedi_desc", 0))
            frete = parse_decimal(getattr(pedido, "pedi_fret", 0))

            total_liquido_sem_credito = total - desconto + frete

            usar_credito = parametros.get("usar_credito")
            if usar_credito in (None, ""):
                usar_credito = parse_decimal(getattr(pedido, "pedi_cred", 0)) > 0

            credito_desejado = parametros.get("valor_credito")
            if credito_desejado in (None, ""):
                credito_desejado = getattr(pedido, "pedi_cred", None)

            credito_aplicado = Decimal("0.00")
            if usar_credito and getattr(pedido, "pedi_clie", None):
                credito_aplicado = CreditoTrocaPisosService.calcular_credito_aplicado(
                    banco=banco,
                    empresa=pedido.pedi_empr,
                    filial=pedido.pedi_fili,
                    cliente_id=pedido.pedi_clie,
                    total_liquido_sem_credito=total_liquido_sem_credito,
                    valor_desejado=credito_desejado,
                    excluir_pedido=pedido.pedi_nume,
                )

            pedido.pedi_cred = credito_aplicado
            pedido.pedi_tota = arredondar(total_liquido_sem_credito - credito_aplicado)

            update_fields = [
                f.name
                for f in pedido._meta.fields
                if f.name not in ("pedi_empr", "pedi_fili", "pedi_nume")
            ]
            update_data = {nome: getattr(pedido, nome) for nome in update_fields}
            updated = Pedidospisos.objects.using(banco).filter(
                pedi_empr=chave[0],
                pedi_fili=chave[1],
                pedi_nume=chave[2],
            ).update(**update_data)
            if updated == 0:
                raise ValueError("Pedido não encontrado para atualização (empresa/filial/número).")

            PedidoCriarService.gerar_titulos_receber(banco=banco, pedido=pedido, parametros=parametros)

            return pedido

    @staticmethod
    def normalizar_erro(exc):
        if DRFValidationError is not None and isinstance(exc, DRFValidationError):
            return getattr(exc, "detail", None) or str(exc)

        if isinstance(exc, DjangoValidationError):
            return getattr(exc, "message_dict", None) or str(exc)

        return str(exc)
