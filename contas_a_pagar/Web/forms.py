from django import forms
from django.core.exceptions import ValidationError
from ..models import Titulospagar


class TitulosPagarForm(forms.ModelForm):
    class Meta:
        model = Titulospagar
        fields = [
            'titu_forn','titu_titu','titu_seri','titu_parc',
            'titu_emis','titu_venc','titu_form_reci','titu_valo', 'titu_cecu'
        ]
        widgets = {
            'titu_forn': forms.NumberInput(attrs={'class': 'form-control'}),
            'titu_titu': forms.TextInput(attrs={'class': 'form-control'}),
            'titu_seri': forms.TextInput(attrs={'class': 'form-control'}),
            'titu_parc': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
            'titu_emis': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'titu_venc': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'titu_form_reci': forms.Select(attrs={'class': 'form-select'}),
            'titu_valo': forms.NumberInput(attrs={'type': 'number', 'step': '0.01', 'class': 'form-control'}),
            'titu_cecu': forms.HiddenInput(),
        }
        unique_together = ()

    def __init__(self, *args, **kwargs):
        bloquear_parcela = kwargs.pop('bloquear_parcela', True)
        super().__init__(*args, **kwargs)
        # Em edição, não permitir alteração de chaves compostas para evitar conflitos de PK/UK
        if getattr(self.instance, 'pk', None):
            bloqueados = ['titu_forn', 'titu_titu', 'titu_seri']
            if bloquear_parcela:
                bloqueados.append('titu_parc')
            for f in bloqueados:
                if f in self.fields:
                    self.fields[f].disabled = True
                    attrs = self.fields[f].widget.attrs
                    attrs['readonly'] = 'readonly'

    def clean(self):
        return self.cleaned_data

