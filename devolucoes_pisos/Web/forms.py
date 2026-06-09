from django import forms

from devolucoes_pisos.models import Devolucoespedidopiso, Creditotrocas


class DevolucaoPedidoPisoForm(forms.ModelForm):
    tipo = forms.ChoiceField(
        choices=[
            ("DEVO", "Devolução"),
            ("TROC", "Troca"),
        ],
        initial="DEVO",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Devolucoespedidopiso
        fields = ["devo_pedi", "devo_data", "devo_desc"]
        widgets = {
            "devo_pedi": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "devo_data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "devo_desc": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }
        

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["devo_desc"].required = False
        self.fields["devo_data"].required = False

        if self.instance and getattr(self.instance, "pk", None):
            self.fields["devo_pedi"].disabled = True


class CreditosForm(forms.ModelForm):
    class Meta:
        model = Creditotrocas
        fields = "__all__"
        widgets = {
            "cred_fina_data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }
        labels = {
            "cred_fina_data": "Data",
            "cred_fina_valo": "Valor",
            "cred_fina_obse": "Observação",
            
        }