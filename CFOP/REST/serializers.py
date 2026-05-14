from rest_framework import serializers

from Entidades.models import Entidades

from ..models import CFOP
from ..models_tributos import Tributos


class CFOPSerializer(serializers.ModelSerializer):
    CAMPOS_PADRAO = [
        "cfop_empr",
        "cfop_codi",
        "cfop_desc",
    ]

    INCIDENCIAS = [
        "cfop_exig_ipi",
        "cfop_exig_icms",
        "cfop_exig_pis_cofins",
        "cfop_exig_cbs",
        "cfop_exig_ibs",
        "cfop_gera_st",
        "cfop_gera_difal",
        "cfop_icms_base_inclui_ipi",
        "cfop_st_base_inclui_ipi",
        "cfop_ipi_tota_nf",
        "cfop_st_tota_nf",
    ]

    class Meta:
        model = CFOP
        fields = [
            "cfop_id",
            "cfop_empr",
            "cfop_codi",
            "cfop_desc",
            "cfop_exig_ipi",
            "cfop_exig_icms",
            "cfop_exig_pis_cofins",
            "cfop_exig_cbs",
            "cfop_exig_ibs",
            "cfop_gera_st",
            "cfop_gera_difal",
            "cfop_icms_base_inclui_ipi",
            "cfop_st_base_inclui_ipi",
            "cfop_ipi_tota_nf",
            "cfop_st_tota_nf",
        ]
        extra_kwargs = {
            "cfop_empr": {"required": False},
        }

    def to_internal_value(self, data):
        if isinstance(data, dict) and ("campos_padrao" in data or "incidencias" in data):
            flat = {}

            for k, v in data.items():
                if k in self.fields:
                    flat[k] = v

            for item in data.get("campos_padrao") or []:
                if not isinstance(item, dict):
                    continue
                campo = item.get("campo")
                if campo in self.CAMPOS_PADRAO:
                    flat[campo] = item.get("valor")

            bool_field = serializers.BooleanField()
            for item in data.get("incidencias") or []:
                if not isinstance(item, dict):
                    continue
                campo = item.get("campo")
                if campo in self.INCIDENCIAS:
                    flat[campo] = bool_field.to_internal_value(item.get("valor"))

            return super().to_internal_value(flat)

        return super().to_internal_value(data)

    def to_representation(self, instance):
        def montar_item(field_name: str):
            field = instance._meta.get_field(field_name)
            return {
                "campo": field_name,
                "valor": getattr(instance, field_name),
                "label": str(getattr(field, "verbose_name", field_name)),
                "help_text": str(getattr(field, "help_text", "")) or "",
            }

        return {
            "cfop_id": instance.cfop_id,
            "campos_padrao": [montar_item(f) for f in self.CAMPOS_PADRAO],
            "incidencias": [montar_item(f) for f in self.INCIDENCIAS],
        }


class TributoSpartacusSerializer(serializers.ModelSerializer):
    empresa = serializers.IntegerField(source="trib_empr", read_only=True)
    filial = serializers.IntegerField(source="trib_fili", read_only=True)
    tipo = serializers.CharField(source="trib_tipo")
    entidade = serializers.ChoiceField(source="trib_enti", choices=Entidades.CLASSIFICACAO_TRIBUTACAO)
    estado = serializers.ChoiceField(source="trib_esta", choices=Tributos._meta.get_field("trib_esta").choices)
    codigo = serializers.CharField(source="trib_codi")
    aliquota_icms = serializers.DecimalField(source="trib_aliq_icms", max_digits=9, decimal_places=4, required=False, allow_null=True)
    reducao_icms = serializers.DecimalField(source="trib_redu_icms", max_digits=9, decimal_places=4, required=False, allow_null=True)
    aliquota_icms_st = serializers.DecimalField(source="trib_aliq_icms_st", max_digits=9, decimal_places=4, required=False, allow_null=True)
    reducao_icms_st = serializers.DecimalField(source="trib_redu_icms_st", max_digits=9, decimal_places=4, required=False, allow_null=True)
    mva_icms_st = serializers.DecimalField(source="trib_mva_icms_st", max_digits=8, decimal_places=2, required=False, allow_null=True)
    cst_icms = serializers.CharField(source="trib_cst_icms", required=False, allow_blank=True, allow_null=True)
    cst_pis = serializers.CharField(source="trib_cst_pis", required=False, allow_blank=True, allow_null=True)
    cst_cofins = serializers.CharField(source="trib_cst_cofi", required=False, allow_blank=True, allow_null=True)
    aliquota_pis = serializers.DecimalField(source="trib_aliq_pis", max_digits=5, decimal_places=2, required=False, allow_null=True)
    aliquota_cofins = serializers.DecimalField(source="trib_aliq_cofi", max_digits=5, decimal_places=2, required=False, allow_null=True)
    cfop = serializers.IntegerField(source="trib_cfop", required=False, allow_null=True)
    cfop_label = serializers.SerializerMethodField()
    entidade_label = serializers.SerializerMethodField()
    estado_label = serializers.SerializerMethodField()

    class Meta:
        model = Tributos
        fields = [
            "empresa",
            "filial",
            "tipo",
            "entidade",
            "entidade_label",
            "estado",
            "estado_label",
            "codigo",
            "aliquota_icms",
            "reducao_icms",
            "aliquota_icms_st",
            "reducao_icms_st",
            "mva_icms_st",
            "cst_icms",
            "cst_pis",
            "cst_cofins",
            "aliquota_pis",
            "aliquota_cofins",
            "cfop",
            "cfop_label",
        ]

    def get_entidade_label(self, instance):
        return instance.get_trib_enti_display()

    def get_estado_label(self, instance):
        return instance.get_trib_esta_display()

    def get_cfop_label(self, instance):
        if not instance.trib_cfop:
            return ""
        try:
            cfop = CFOP.objects.using(instance._state.db).filter(cfop_id=instance.trib_cfop).only('cfop_codi', 'cfop_desc').first()
            if cfop:
                return f"{cfop.cfop_codi} • {cfop.cfop_desc}"
        except Exception:
            pass
        return str(instance.trib_cfop)


class TributoSpartacusCloneSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    codigo_destino = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tipo = serializers.CharField(required=False, allow_blank=True, default="P")
    origem_estado = serializers.ChoiceField(choices=Tributos._meta.get_field("trib_esta").choices)
    origem_entidade = serializers.ChoiceField(choices=Entidades.CLASSIFICACAO_TRIBUTACAO)
    estados_destino = serializers.ListField(
        child=serializers.ChoiceField(choices=Tributos._meta.get_field("trib_esta").choices),
        required=False,
        allow_empty=True,
    )
    entidades_destino = serializers.ListField(
        child=serializers.ChoiceField(choices=Entidades.CLASSIFICACAO_TRIBUTACAO),
        required=False,
        allow_empty=True,
    )
