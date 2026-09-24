from rest_framework import serializers
from ..models import PerfilOcorrencia, OcorrenciaTransp

class OcorrenciaSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(source="ocor_codi", read_only=True)
    descricao = serializers.CharField(source="ocor_desc", read_only=True)

    class Meta:
        model = OcorrenciaTransp
        fields = ["id", "codigo", "descricao"]


class PerfilSerializer(serializers.ModelSerializer):
    descricao = serializers.CharField(source="pfoc_desc", read_only=True)
    ativo = serializers.BooleanField(source="pfoc_ativ", required=False)

    ocorrencias = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=OcorrenciaTransp.objects.all()
    )

    class Meta:
        model = PerfilOcorrencia
        fields = [
            "id",
            "empresa",
            "filial",
            "descricao",
            "ativo",
            "ocorrencias",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["ocorrencias"] = OcorrenciaSerializer(
            instance.ocorrencias.all(), 
            many=True
        ).data
        return representation