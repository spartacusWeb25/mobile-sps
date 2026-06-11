# Localidades/rest/serializers.py

from rest_framework import serializers

from localidades.models import Estados, Paises, Cidades


class MultiBancoModelSerializer(serializers.ModelSerializer):
    """
    Serializer base que respeita o banco da licença (multibanco).
    O viewset injeta 'banco' no contexto.
    """

    @property
    def banco(self):
        return self.context.get("banco", "default")

    def create(self, validated_data):
        instancia = self.Meta.model(**validated_data)
        instancia.save(using=self.banco)
        return instancia

    def update(self, instance, validated_data):
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.save(using=self.banco)
        return instance


class EstadosSerializer(MultiBancoModelSerializer):
    codigo = serializers.IntegerField(source="esta_codi")
    nome = serializers.CharField(source="esta_nome", max_length=255)
    sigla = serializers.CharField(source="esta_sigl", max_length=2)

    class Meta:
        model = Estados
        fields = ["codigo", "nome", "sigla"]


class PaisesSerializer(MultiBancoModelSerializer):
    codigo = serializers.IntegerField(source="pais_codi")
    nome = serializers.CharField(source="pais_nome", max_length=255)
    observacoes = serializers.CharField(
        source="pais_obse", required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = Paises
        fields = ["codigo", "nome", "observacoes"]


class CidadesSerializer(MultiBancoModelSerializer):
    codigo_ibge = serializers.IntegerField(source="cida_codi")
    nome = serializers.CharField(source="cida_nome", max_length=255)
    sigla = serializers.CharField(source="cida_sigl", max_length=2)
    frete = serializers.IntegerField(
        source="cida_fret", required=False, allow_null=True
    )

    estado = serializers.PrimaryKeyRelatedField(
        source="cida_esta", queryset=Estados.objects.none()
    )
    pais = serializers.PrimaryKeyRelatedField(
        source="cida_pais", queryset=Paises.objects.none()
    )

    # Leitura amigável
    estado_nome = serializers.CharField(source="cida_esta.esta_nome", read_only=True)
    estado_sigla = serializers.CharField(source="cida_esta.esta_sigl", read_only=True)
    pais_nome = serializers.CharField(source="cida_pais.pais_nome", read_only=True)

    class Meta:
        model = Cidades
        fields = [
            "codigo_ibge",
            "nome",
            "sigla",
            "frete",
            "estado",
            "pais",
            "estado_nome",
            "estado_sigla",
            "pais_nome",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajusta os querysets das FKs para o banco da licença
        self.fields["estado"].queryset = Estados.objects.using(self.banco).all()
        self.fields["pais"].queryset = Paises.objects.using(self.banco).all()
