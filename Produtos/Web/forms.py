
from django import forms
import Produtos
from Produtos.models import Ncm
from Produtos.models import NcmAliquota, Produtos, UnidadeMedida


class NcmAliquotaForm(forms.ModelForm):
    class Meta:
        model = NcmAliquota
        fields = [
            "nali_ncm",
            "nali_aliq_ipi",
            "nali_aliq_pis",
            "nali_aliq_cofins",
            "nali_aliq_cbs",
            "nali_aliq_ibs",
        ]

        widgets = {
            "nali_ncm": forms.TextInput(attrs={"class": "form-control", "placeholder": "Código NCM", "list": "ncm-codes"}),
            "nali_aliq_ipi": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "nali_aliq_pis": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "nali_aliq_cofins": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "nali_aliq_cbs": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "nali_aliq_ibs": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        self.database = kwargs.pop('database', 'default')
        super().__init__(*args, **kwargs)
        try:
            if 'nali_ncm' in self.fields:
                self.fields['nali_ncm'].queryset = Ncm.objects.using(self.database).all().order_by('ncm_codi')
        except Exception:
            pass

    def clean_nali_ncm(self):
        value = self.cleaned_data.get('nali_ncm')
        if isinstance(value, Ncm):
            return value
        codigo = str(value or '').strip()
        if not codigo:
            raise forms.ValidationError('Informe o NCM')
        obj = Ncm.objects.using(self.database).filter(ncm_codi=codigo).first()
        if not obj:
            raise forms.ValidationError('NCM inválido')
        return obj


class NcmForm(forms.ModelForm):
    class Meta:
        model = Ncm
        fields = [
            "ncm_codi",
            "ncm_desc",
        ]
        widgets = {
            "ncm_codi": forms.TextInput(attrs={"class": "form-control", "placeholder": "Código NCM"}),
            "ncm_desc": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Descrição"}),
        }

    def clean_ncm_codi(self):
        codigo = (self.cleaned_data.get("ncm_codi") or "").strip()
        if not codigo:
            raise forms.ValidationError("Informe o código NCM.")
        if len(codigo) > 10:
            raise forms.ValidationError("Código NCM deve ter até 10 caracteres.")
        return codigo




class ServicosForm(forms.ModelForm):
    prod_unme_autocomplete = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )
    prod_cnae = forms.CharField(required=False, widget=forms.HiddenInput())
    prod_codi_serv = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Produtos
        fields = [
            'prod_unme',
            'prod_e_serv', 
            'prod_exig_iss', 
            'prod_iss', 
            'prod_codi_serv', 
            'prod_desc_serv', 
            'prod_cnae', 
            'prod_list_tabe_prec',

        ]
        widgets = {
            "prod_unme": forms.HiddenInput(),
            "prod_e_serv": forms.HiddenInput(),
            "prod_desc_serv": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Descrição"}),
            "prod_cnae": forms.Select(attrs={"class": "form-control"}),
            "prod_codi_serv": forms.Select(attrs={"class": "form-control"}),
            "prod_list_tabe_prec": forms.Select(attrs={"class": "form-control"}),
            "prod_exig_iss": forms.Select(attrs={"class": "form-control"}),
            "prod_iss": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Alíquota ISS"}),
        }
        
        labels = {
            "prod_unme": "Unidade de Medida",
            "prod_e_serv": "Tipo de Serviço",
            "prod_exig_iss": "Exige ISS",
            "prod_iss": "ISS",
            "prod_codi_serv": "Código de Serviço",
            "prod_desc_serv": "Descrição",
            "prod_cnae": "CNAE",
            "prod_list_tabe_prec": "Lista de Preços",
        }
        help_texts = {
            "prod_unme": "Informe a unidade de medida do produto.",
            "prod_e_serv": "Informe o tipo de serviço do produto.",
            "prod_exig_iss": "Informe se o produto exige ISS.",
            "prod_iss": "Informe o ISS do produto.",
            "prod_codi_serv": "Informe o código de serviço do produto.",
            "prod_desc_serv": "Informe a descrição do produto.",
            "prod_cnae": "Informe o CNAE do produto.",
            "prod_list_tabe_prec": "Informe a lista de preços do produto.",
        }

    def __init__(self, *args, **kwargs):
        self.database = kwargs.pop('database', 'default')
        super().__init__(*args, **kwargs)
        self.fields['prod_unme_autocomplete'].label = 'Unidade de Medida'
        self.fields['prod_unme_autocomplete'].help_text = 'Digite e selecione a unidade de medida.'
        self.fields['prod_unme_autocomplete'].initial = self.instance.prod_unme_id if getattr(self.instance, 'prod_unme_id', None) else ''

        if 'prod_unme' in self.fields:
            self.fields['prod_unme'].required = False
            try:
                self.fields['prod_unme'].queryset = UnidadeMedida.objects.using(self.database).all().order_by('unid_desc')
            except Exception:
                pass

        self.cnae_choices = [
            ('0111-3/01', '0111-3/01 - Cultivo de cereais'),
            ('6201-5/01', '6201-5/01 - Desenvolvimento de programas de computador sob encomenda'),
            ('7490-1/99', '7490-1/99 - Outras atividades profissionais, científicas e técnicas'),
        ]
        self.servico_choices = [
            ('1.01', '1.01 - Análise e desenvolvimento de sistemas'),
            ('1.02', '1.02 - Programação'),
            ('1.03', '1.03 - Processamento de dados e congêneres'),
        ]
        if 'prod_cnae' in self.fields:
            self.fields['prod_cnae'].choices = self.cnae_choices
        if 'prod_codi_serv' in self.fields:
            self.fields['prod_codi_serv'].choices = self.servico_choices
        if 'prod_list_tabe_prec' in self.fields:
            self.fields['prod_list_tabe_prec'].required = False
            self.fields['prod_list_tabe_prec'].queryset = Produtos.objects.using(self.database).none()

    def clean_prod_unme(self):
        codigo = (self.cleaned_data.get('prod_unme_autocomplete') or self.data.get('prod_unme_autocomplete') or '').strip().upper()
        if not codigo:
            raise forms.ValidationError('Informe a unidade de medida.')
        unidade = UnidadeMedida.objects.using(self.database).filter(unid_codi=codigo).first()
        if not unidade:
            raise forms.ValidationError('Unidade de medida inválida.')
        return unidade

    def clean_prod_iss(self):
        valor = self.cleaned_data.get('prod_iss')
        if valor in (None, ''):
            return None
        return valor

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['prod_e_serv'] = True
        return cleaned_data
       
