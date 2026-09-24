from django import forms
from ..models import OcorrenciaTransp, PerfilOcorrencia

class OcorrenciaForm(forms.ModelForm):
    class Meta:
        model = OcorrenciaTransp
        fields = ['ocor_codi', 'ocor_desc', 'ocor_fina']
        widgets = {
            'ocor_codi': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'ocor_desc': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'ocor_fina': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'ocor_codi': 'Código',
            'ocor_desc': 'Descrição',
            'ocor_fina': 'Finalizadora',
        }

class PerfilOcorrenciaForm(forms.ModelForm):
    class Meta:
        model = PerfilOcorrencia
        fields = ['pfoc_desc', 'pfoc_ativ']
        widgets = {
            'pfoc_desc': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'pfoc_ativ': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'pfoc_desc': 'Descrição',
            'pfoc_ativ': 'Ativo',
        }