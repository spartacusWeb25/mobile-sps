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
    beneficio_fiscal = forms.CharField(required=False, max_length=10)

    ibscbs_cclasstrib = forms.CharField(required=False, max_length=6)
    ibscbs_cst = forms.CharField(required=False, max_length=3)
    ibs_paliqefetuf = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    ibs_pibsuf = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    ibs_pdifmun = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    ibs_paliqefetmun = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    ibs_predmun = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    adremibsret = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    cbs_paliqefetreg = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    cbs_pcbs = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    ibs_paliqefetmunreg = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    ibs_paliqefetufreg = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    ibscbs_cclasstribreg = forms.CharField(required=False, max_length=6)
    ibscbs_cstreg = forms.CharField(required=False, max_length=3)
    ibscbs_cstregid = forms.IntegerField(required=False)

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
            "beneficio_fiscal": data.get("beneficio_fiscal"),
            "ibscbs": {
                "cclasstrib": data.get("ibscbs_cclasstrib"),
                "cst": data.get("ibscbs_cst"),
                "ibs_paliqefetuf": data.get("ibs_paliqefetuf"),
                "ibs_pibsuf": data.get("ibs_pibsuf"),
                "ibs_pdifmun": data.get("ibs_pdifmun"),
                "ibs_paliqefetmun": data.get("ibs_paliqefetmun"),
                "ibs_predmun": data.get("ibs_predmun"),
                "adremibsret": data.get("adremibsret"),
                "cbs_paliqefetreg": data.get("cbs_paliqefetreg"),
                "cbs_pcbs": data.get("cbs_pcbs") if data.get("cbs_pcbs") not in (None, "") else data.get("cbs_paliqefetreg"),
                "ibs_paliqefetmunreg": data.get("ibs_paliqefetmunreg"),
                "ibs_paliqefetufreg": data.get("ibs_paliqefetufreg"),
                "cclasstribreg": data.get("ibscbs_cclasstribreg"),
                "cstreg": data.get("ibscbs_cstreg"),
                "cstregid": data.get("ibscbs_cstregid"),
            },
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
            "beneficio_fiscal": getattr(instance, "trib_codi_bene", None),
            "ibscbs_cclasstrib": getattr(instance, "trib_ibscbs_cclasstrib", None),
            "ibscbs_cst": getattr(instance, "trib_ibscbs_cst", None),
            "ibs_paliqefetuf": getattr(instance, "trib_ibs_paliqefetuf", None),
            "ibs_pibsuf": getattr(instance, "trib_ibs_pibsuf", None),
            "ibs_pdifmun": getattr(instance, "trib_ibs_pdifmun", None),
            "ibs_paliqefetmun": getattr(instance, "trib_ibs_paliqefetmun", None),
            "ibs_predmun": getattr(instance, "trib_ibs_predmun", None),
            "adremibsret": getattr(instance, "trib_adremibsret", None),
            "cbs_paliqefetreg": getattr(instance, "trib_cbs_paliqefetreg", None),
            "cbs_pcbs": getattr(instance, "trib_cbs_pcbs", None),
            "ibs_paliqefetmunreg": getattr(instance, "trib_ibs_paliqefetmunreg", None),
            "ibs_paliqefetufreg": getattr(instance, "trib_ibs_paliqefetufreg", None),
            "ibscbs_cclasstribreg": getattr(instance, "trib_ibscbs_cclasstribreg", None),
            "ibscbs_cstreg": getattr(instance, "trib_ibscbs_cstreg", None),
            "ibscbs_cstregid": getattr(instance, "trib_ibscbs_cstregid", None),
        }
