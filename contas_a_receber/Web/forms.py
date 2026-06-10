from django import forms
from ..models import Titulosreceber


class TitulosReceberForm(forms.ModelForm):
    class Meta:
        model = Titulosreceber
        fields = ['titu_clie', 'titu_seri', 'titu_parc', 'titu_valo', 'titu_emis', 'titu_venc', 'titu_form_reci', 'titu_titu', 'titu_cecu']
        widgets = {
            'titu_clie': forms.NumberInput(attrs={'class': 'form-control'}),
            'titu_seri': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 5}),
            'titu_parc': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
            'titu_valo': forms.NumberInput(attrs={'type': 'number', 'step': '0.01', 'class': 'form-control'}),
            'titu_emis': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'titu_venc': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'titu_form_reci': forms.Select(attrs={'class': 'form-select'}),
            'titu_titu': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 13}),
            'titu_cecu': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        bloquear_parcela = kwargs.pop('bloquear_parcela', True)
        super().__init__(*args, **kwargs)
        if getattr(self.instance, 'pk', None):
            bloqueados = ['titu_clie', 'titu_titu', 'titu_seri']
            if bloquear_parcela:
                bloqueados.append('titu_parc')
            for campo in bloqueados:
                if campo in self.fields:
                    self.fields[campo].disabled = True
                    self.fields[campo].widget.attrs['readonly'] = 'readonly'

    def clean(self):
        return self.cleaned_data
