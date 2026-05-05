from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.exceptions import ValidationError
from planos.service import PlanoService
import logging
import re

logger = logging.getLogger(__name__)

class TrialSignupSerializer(serializers.Serializer):
    nome_empresa = serializers.CharField(max_length=100)
    cnpj = serializers.CharField(max_length=14)
    email = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    nome_fantasia = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    telefone = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=14)
    endereco = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=60)
    cidade = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=60)
    uf = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=2)
    nome_filial = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    modulos = serializers.ListField(
        required=False,
        allow_empty=True,
        child=serializers.CharField(max_length=100),
    )

    def validate_cnpj(self, value):
        raw = (value or "").strip()
        if not raw:
            raise serializers.ValidationError("Este campo é obrigatório.")
        digits = re.sub(r"\D", "", raw)
        if len(digits) != 14:
            raise serializers.ValidationError("CNPJ inválido. Informe 14 dígitos.")
        return digits


class TrialSignupView(APIView):
    """
    Endpoint para criar um novo ambiente de teste (Trial).
    Recebe:
    {
        "nome_empresa": "Minha Empresa",
        "cnpj": "00000000000000",
        "email": "admin@empresa.com",
        "nome_fantasia": "Minha Empresa Fantasia", # Opcional
        "telefone": "11999999999", # Opcional
        "endereco": "Rua X", # Opcional
        "cidade": "Cidade", # Opcional
        "uf": "SP", # Opcional
        "nome_filial": "Matriz" # Opcional
    }
    """
    permission_classes = [] # Aberto para cadastro
    authentication_classes = []

    def post(self, request):
        serializer = TrialSignupSerializer(data=request.data)
        if not serializer.is_valid():
            try:
                logger.warning(
                    "TrialSignupView payload_invalido errors=%s keys=%s",
                    serializer.errors,
                    sorted(list(getattr(request.data, "keys", lambda: [])())),
                )
            except Exception:
                logger.warning("TrialSignupView payload_invalido errors=%s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        dados = serializer.validated_data
        modulos = dados.pop('modulos', [])

        nome = dados.get('nome_empresa')
        cnpj = dados.get('cnpj')
        logger.info(f"Iniciando criação de trial para {nome} ({cnpj})")

        try:
            result = PlanoService.criar_ambiente_trial(dados, modulos_liberados=modulos)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Erro no signup trial: {e}", exc_info=True)
            return Response({"error": "Erro interno ao processar solicitação."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                "message": "Ambiente criado com sucesso!",
                "slug": result["licenca"].slug,
                "db_name": result["licenca"].db_name,
                "plano": result["plano"].plan_nome,
                "usuario": result["usuario"].usua_nome,
                "senha_inicial": "123mudar",
            },
            status=status.HTTP_201_CREATED,
        )
