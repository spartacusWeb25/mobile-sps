# cadastro_rapido_simplificado.py

from django.core.exceptions import ValidationError
from ..models import Entidades
from ..utils import proxima_entidade


class EntidadeCadastroRapidoSimplificado:

    @staticmethod
    def cadastrar_rapido_simplificado(*, data, empresa_id,banco):
        """
        Service de cadastro rápido simplificado que aceita apenas:
        - Nome
        - Telefone
        - E-mail
        
        Não requer CPF, CEP ou endereço.
        """
        nome = data.get("enti_nome", "").strip()
        telefone = data.get("enti_fone", "").strip()
        email = data.get("enti_ema1", "").strip()

        if not nome:
            raise ValidationError("Nome é obrigatório")

        proximo_clie = proxima_entidade(empresa_id, banco)

        return Entidades.objects.using(banco).create(
            enti_nome=nome,
            enti_fant=nome,
            enti_clie=proximo_clie,
            enti_fone=telefone or None,
            enti_emai=email or None,
            enti_tipo_enti="AM",
            enti_empr=empresa_id,
        )
