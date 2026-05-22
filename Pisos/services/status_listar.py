from Pisos.models import StatusPisos
from Pisos.services.orcamento_atualizar_service import OrcamentoAtualizarService

try:
    from rest_framework.exceptions import ValidationError as DRFValidationError
except Exception:
    DRFValidationError = None

from django.core.exceptions import ValidationError as DjangoValidationError

class StatusPisosServices:

    @staticmethod
    def listar_status(banco, empresa, filial, tipo):
        return StatusPisos.objects.using(banco).filter(
            stat_empr=empresa,
            stat_fili=filial,
            stat_tipo=tipo,
            stat_ativo=True,
        ).order_by("stat_codigo")

    @staticmethod
    def get_status_atual(banco, empresa, filial, tipo, codigo):
        if codigo is None:
            return None

        return StatusPisos.objects.using(banco).filter(
            stat_empr=empresa,
            stat_fili=filial,
            stat_tipo=tipo,
            stat_codigo=codigo,
            stat_ativo=True,
        ).first()

    def executar(self, *, banco, orcamento, dados, itens):
        return OrcamentoAtualizarService().executar(
            banco=banco,
            orcamento=orcamento,
            dados=dados,
            itens=itens,
        )

    @staticmethod
    def normalizar_erro(exc):
        if DRFValidationError is not None and isinstance(exc, DRFValidationError):
            return getattr(exc, "detail", None) or str(exc)
        if isinstance(exc, DjangoValidationError):
            return getattr(exc, "message_dict", None) or str(exc)
        return str(exc)