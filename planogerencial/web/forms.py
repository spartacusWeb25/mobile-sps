from django import forms

from planogerencial.models import PlanoGerencialMascara, PlanoGerencialConta
from planogerencial.services.mascara_service import MascaraGerencialService


class PlanoGerencialMascaraForm(forms.ModelForm):
    class Meta:
        model = PlanoGerencialMascara
        fields = ["gere_nome", "gere_nive", "gere_ativ"]
        widgets = {
            "gere_nome": forms.TextInput(attrs={"class": "form-control"}),
            "gere_nive": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 8,
            }),
            "gere_ativ": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop("empresa")
        super().__init__(*args, **kwargs)

    def clean_gere_nive(self):
        niveis = self.cleaned_data["gere_nive"]
        return MascaraGerencialService.validar_niveis(niveis)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.gere_empr = self.empresa

        if commit:
            obj.save()

        return obj


class PlanoGerencialForm(forms.Form):
    nome = forms.CharField(
        label="Nome da conta",
        max_length=60,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex: Receita de vendas",
        }),
    )

    parent_redu = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )


class PlanoGerencialEditarForm(forms.ModelForm):
    class Meta:
        model = PlanoGerencialConta
        fields = ["gere_nome", "gere_inat", "gere_natu", "gere_dre", "gere_natu_sped", "gere_obse"]
        widgets = {
            "gere_nome": forms.TextInput(attrs={"class": "form-control"}),
            "gere_inat": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "gere_natu": forms.TextInput(attrs={"class": "form-control"}),
            "gere_dre": forms.TextInput(attrs={"class": "form-control"}),
            "gere_natu_sped": forms.TextInput(attrs={"class": "form-control"}),
            "gere_obse": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }