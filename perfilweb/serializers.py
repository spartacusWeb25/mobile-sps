from rest_framework import serializers
from perfilweb.models import Perfil, PermissaoPerfil
from core.serializers import BancoContextMixin

class PermissaoPerfilDetalhadoSerializer(BancoContextMixin, serializers.Serializer):
    app = serializers.CharField()
    model = serializers.CharField()
    acao = serializers.CharField()

    class Meta:
        fields = ['app', 'model', 'acao']