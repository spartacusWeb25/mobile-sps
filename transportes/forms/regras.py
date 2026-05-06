from django import forms
from transportes.models import RegraICMS, RegraPISCOFINS, RegraIBSCBS
from CFOP.models import CFOP
from core.utils import get_licenca_db_config


PIS_COFINS_CST_CHOICES = [
    ("", "---------"),
    ("01", "01 - Operação tributável com alíquota básica"),
    ("02", "02 - Operação tributável com alíquota diferenciada"),
    ("03", "03 - Operação tributável por unidade de medida"),
    ("04", "04 - Operação monofásica"),
    ("05", "05 - Substituição tributária"),
    ("06", "06 - Alíquota zero"),
    ("07", "07 - Isenta"),
    ("08", "08 - Sem incidência"),
    ("09", "09 - Suspensão"),
    ("49", "49 - Outras operações de saída"),
    ("50", "50 - Crédito vinculado exclusivamente à receita tributada"),
    ("51", "51 - Crédito vinculado exclusivamente à receita não tributada"),
    ("52", "52 - Crédito vinculado exclusivamente à receita de exportação"),
    ("53", "53 - Crédito vinculado a receitas tributadas e não tributadas"),
    ("54", "54 - Crédito vinculado a receitas tributadas e exportação"),
    ("55", "55 - Crédito vinculado a receitas não tributadas e exportação"),
    ("56", "56 - Crédito vinculado a receitas tributadas, não tributadas e exportação"),
    ("60", "60 - Crédito presumido vinculado à receita tributada"),
    ("61", "61 - Crédito presumido vinculado à receita não tributada"),
    ("62", "62 - Crédito presumido vinculado à receita de exportação"),
    ("63", "63 - Crédito presumido vinculado a receitas tributadas e não tributadas"),
    ("64", "64 - Crédito presumido vinculado a receitas tributadas e exportação"),
    ("65", "65 - Crédito presumido vinculado a receitas não tributadas e exportação"),
    ("66", "66 - Crédito presumido vinculado a receitas tributadas, não tributadas e exportação"),
    ("67", "67 - Crédito presumido - outras operações"),
    ("70", "70 - Operação sem direito a crédito"),
    ("71", "71 - Operação com isenção"),
    ("72", "72 - Operação com suspensão"),
    ("73", "73 - Operação com alíquota zero"),
    ("74", "74 - Operação sem incidência"),
    ("75", "75 - Operação por substituição tributária"),
    ("98", "98 - Outras operações de entrada"),
    ("99", "99 - Outras operações"),
]

IBS_CBS_CST_CHOICES = [
    ("", "---------"),
    ("000", "000 - Tributação integral"),
    ("010", "010 - Tributação com alíquotas uniformes"),
    ("011", "011 - Tributação com alíquotas uniformes reduzidas"),
    ("200", "200 - Alíquota reduzida"),
    ("210", "210 - Redução com redutor de base"),
    ("220", "220 - Alíquota fixa"),
    ("221", "221 - Alíquota fixa proporcional"),
    ("222", "222 - Redução de alíquota fixa"),
    ("400", "400 - Isenção"),
    ("410", "410 - Imunidade e não incidência"),
    ("510", "510 - Diferimento"),
    ("550", "550 - Suspensão"),
    ("620", "620 - Tributação monofásica"),
    ("800", "800 - Transferência de crédito"),
    ("810", "810 - Ajustes"),
    ("820", "820 - Tributação em declaração de regime específico"),
    ("830", "830 - Exclusão de base"),
]

ESTADOS_CHOICES = [
    ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
    ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
    ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins'),
    ('EX', 'Exterior')
]

CST_CHOICES = [
    ("", "---------"),
    ("00", "00 - Tributada integralmente"),
    ("10", "10 - Tributada com cobrança de ICMS por ST"),
    ("20", "20 - Com redução de base de cálculo"),
    ("30", "30 - Isenta/não tributada com cobrança de ICMS por ST"),
    ("40", "40 - Isenta"),
    ("41", "41 - Não tributada"),
    ("50", "50 - Suspensão"),
    ("51", "51 - Diferimento"),
    ("60", "60 - ICMS cobrado anteriormente por ST"),
    ("70", "70 - Redução de base com cobrança por ST"),
    ("90", "90 - Outros"),
]

CSOSN_CHOICES = [
    ("", "---------"),
    ("101", "101 - Tributada com permissão de crédito"),
    ("102", "102 - Tributada sem permissão de crédito"),
    ("103", "103 - Isenção no SN para faixa de receita"),
    ("201", "201 - Tributada com crédito e com ST"),
    ("202", "202 - Tributada sem crédito e com ST"),
    ("203", "203 - Isenção no SN para faixa e com ST"),
    ("300", "300 - Imune"),
    ("400", "400 - Não tributada pelo SN"),
    ("500", "500 - ICMS cobrado anteriormente por ST"),
    ("900", "900 - Outros"),
]

class RegraICMSForm(forms.ModelForm):
    cfop = forms.ModelChoiceField(
        queryset=CFOP.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='CFOP (Opcional)'
    )
    
    uf_origem = forms.ChoiceField(
        choices=ESTADOS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    uf_destino = forms.ChoiceField(
        choices=ESTADOS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    cst = forms.ChoiceField(
        choices=CST_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="CST",
    )

    csosn = forms.ChoiceField(
        choices=CSOSN_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="CSOSN (Simples)",
    )

    class Meta:
        model = RegraICMS
        fields = '__all__'
        widgets = {
            'aliquota': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'aliquota_destino': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reducao_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'mva_st': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'aliquota_st': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reducao_base_st': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'contribuinte': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'simples_nacional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'diferimento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'isento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Configura queryset do CFOP baseado no banco do tenant
        if self.request:
            db_alias = get_licenca_db_config(self.request)
            self.fields['cfop'].queryset = CFOP.objects.using(db_alias).all().order_by('cfop_codi')
        elif self.instance and self.instance.pk:
            # Tenta pegar do state se não tiver request (fallback)
            db_alias = self.instance._state.db or 'default'
            self.fields['cfop'].queryset = CFOP.objects.using(db_alias).all().order_by('cfop_codi')
        else:
             # Fallback final para default se nada mais funcionar, mas idealmente request deve ser passado
             self.fields['cfop'].queryset = CFOP.objects.using('default').all().order_by('cfop_codi')
        
        # Set initial value for CFOP if instance exists
        if self.instance and self.instance.pk and self.instance.cfop:
            # Pega o alias do queryset configurado acima
            db_alias = self.fields['cfop'].queryset.db
            try:
                cfop_obj = CFOP.objects.using(db_alias).filter(cfop_codi=self.instance.cfop).first()
                if cfop_obj:
                    self.initial['cfop'] = cfop_obj
            except Exception:
                pass

        is_simples = bool(self.instance.simples_nacional) if getattr(self.instance, "pk", None) else False
        if self.data:
            key = self.add_prefix("simples_nacional")
            is_simples = self.data.get(key) in {"on", "true", "True", "1"}

        self.fields["csosn"].required = is_simples
        self.fields["cst"].required = not is_simples

    def clean_cfop(self):
        cfop = self.cleaned_data.get('cfop')
        # Se for ModelChoiceField, cfop já é o objeto ou None
        # Precisamos retornar o ID ou string que o model espera, ou o próprio objeto se o model suportar
        # O model RegraICMS tem cfop como CharField ou IntegerField? 
        # No código anterior era TextInput com maxlength 4, indicando que pode ser string.
        # Mas o model CFOP tem cfop_codi. 
        # Vamos verificar o model RegraICMS novamente.
        # Se o model espera o código (ex: '5102'), devemos retornar cfop.cfop_codi
        if cfop:
            return cfop.cfop_codi
        return None

    def clean(self):
        cleaned_data = super().clean()
        is_simples = bool(cleaned_data.get("simples_nacional"))

        if is_simples:
            csosn = (cleaned_data.get("csosn") or "").strip()
            if not csosn:
                self.add_error("csosn", "Informe o CSOSN.")
            cst = (cleaned_data.get("cst") or "").strip()
            cleaned_data["cst"] = cst or "00"
        else:
            cst = (cleaned_data.get("cst") or "").strip()
            if not cst:
                self.add_error("cst", "Informe o CST.")
            cleaned_data["csosn"] = None

        return cleaned_data

class RegraPISCOFINSForm(forms.ModelForm):
    pis_cst = forms.ChoiceField(
        choices=PIS_COFINS_CST_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="CST PIS",
    )

    cofins_cst = forms.ChoiceField(
        choices=PIS_COFINS_CST_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="CST COFINS",
    )

    class Meta:
        model = RegraPISCOFINS
        exclude = ["empresa", "uf_origem", "uf_destino", "cfop", "simples_nacional"]
        widgets = {
            "pis_aliquota": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cofins_aliquota": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class RegraIBSCBSForm(forms.ModelForm):
    cst = forms.ChoiceField(
        choices=IBS_CBS_CST_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="CST IBS/CBS",
    )

    class Meta:
        model = RegraIBSCBS
        exclude = ["empresa", "uf_origem", "uf_destino", "cfop"]
        widgets = {
            "cclasstrib": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: 000001"}),
            "aliquota_cbs": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "aliquota_ibs_uf": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "aliquota_ibs_mun": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "reducao_cbs": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "reducao_ibs_uf": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "reducao_ibs_mun": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
