from django import forms

from Entidades.models import Entidades

from ..models_tributos import Tributos


class TributoForm(forms.ModelForm):
    empresa = forms.IntegerField(required=False)
    filial = forms.IntegerField(required=False)
    tipo = forms.CharField(initial="P")
    entidade = forms.ChoiceField(choices=Entidades.CLASSIFICACAO_TRIBUTACAO)
    estado = forms.ChoiceField(choices=Tributos._meta.get_field("trib_esta").choices)
    codigo = forms.CharField(max_length=20)

    aliquota_icms = forms.DecimalField(required=False, max_digits=9, decimal_places=4)
    reducao_icms = forms.DecimalField(required=False, max_digits=9, decimal_places=4)
    aliquota_icms_st = forms.DecimalField(required=False, max_digits=9, decimal_places=4)
    reducao_icms_st = forms.DecimalField(required=False, max_digits=9, decimal_places=4)
    mva_icms_st = forms.DecimalField(required=False, max_digits=8, decimal_places=2)

    cst_icms = forms.CharField(required=False, max_length=3)
    cst_pis = forms.CharField(required=False, max_length=3)
    cst_cofins = forms.CharField(required=False, max_length=3)
    aliquota_pis = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    aliquota_cofins = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    cfop = forms.IntegerField(required=False)

    class Meta:
        model = Tributos
        fields = []

    def clean_tipo(self):
        return str(self.cleaned_data.get("tipo") or "P").strip().upper()[:1] or "P"

    def clean_codigo(self):
        return str(self.cleaned_data.get("codigo") or "").strip()

    def clean_estado(self):
        return str(self.cleaned_data.get("estado") or "").strip().upper()

    def clean_entidade(self):
        return str(self.cleaned_data.get("entidade") or "").strip().upper()

    def to_service_data(self):
        data = self.cleaned_data
        return {
            "empresa": data.get("empresa"),
            "filial": data.get("filial"),
            "tipo": data["tipo"],
            "entidade": data["entidade"],
            "estado": data["estado"],
            "codigo": data["codigo"],
            "icms": {
                "aliquota": data.get("aliquota_icms"),
                "reducao": data.get("reducao_icms"),
                "cst": data.get("cst_icms"),
            },
            "icms_st": {
                "aliquota": data.get("aliquota_icms_st"),
                "reducao": data.get("reducao_icms_st"),
                "mva": data.get("mva_icms_st"),
            },
            "pis": {
                "cst": data.get("cst_pis"),
                "aliquota": data.get("aliquota_pis"),
            },
            "cofins": {
                "cst": data.get("cst_cofins"),
                "aliquota": data.get("aliquota_cofins"),
            },
            "cfop": data.get("cfop"),
        }

    @classmethod
    def initial_from_instance(cls, instance: Tributos) -> dict:
        return {
            "empresa": getattr(instance, "trib_empr", None),
            "filial": getattr(instance, "trib_fili", None),
            "tipo": getattr(instance, "trib_tipo", None),
            "entidade": getattr(instance, "trib_enti", None),
            "estado": getattr(instance, "trib_esta", None),
            "codigo": getattr(instance, "trib_codi", None),
            "aliquota_icms": getattr(instance, "trib_aliq_icms", None),
            "reducao_icms": getattr(instance, "trib_redu_icms", None),
            "aliquota_icms_st": getattr(instance, "trib_aliq_icms_st", None),
            "reducao_icms_st": getattr(instance, "trib_redu_icms_st", None),
            "mva_icms_st": getattr(instance, "trib_mva_icms_st", None),
            "cst_icms": getattr(instance, "trib_cst_icms", None),
            "cst_pis": getattr(instance, "trib_cst_pis", None),
            "cst_cofins": getattr(instance, "trib_cst_cofi", None),
            "aliquota_pis": getattr(instance, "trib_aliq_pis", None),
            "aliquota_cofins": getattr(instance, "trib_aliq_cofi", None),
            "cfop": getattr(instance, "trib_cfop", None),
        }
