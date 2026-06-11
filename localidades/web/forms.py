# Localidades/web/forms.py

from django import forms

from localidades.models import Estados, Paises, Cidades


class EstadosForm(forms.ModelForm):

    class Meta:
        model = Estados
        fields = ["esta_codi", "esta_nome", "esta_sigl"]
        labels = {
            "esta_codi": "Código",
            "esta_nome": "Nome",
            "esta_sigl": "Sigla (UF)",
        }
        widgets = {
            "esta_codi": forms.NumberInput(attrs={"class": "form-control"}),
            "esta_nome": forms.TextInput(attrs={"class": "form-control"}),
            "esta_sigl": forms.TextInput(
                attrs={"class": "form-control text-uppercase", "maxlength": 2}
            ),
        }

    def clean_esta_sigl(self):
        return (self.cleaned_data.get("esta_sigl") or "").strip().upper()

    def clean_esta_nome(self):
        return (self.cleaned_data.get("esta_nome") or "").strip()


class PaisesForm(forms.ModelForm):

    class Meta:
        model = Paises
        fields = ["pais_codi", "pais_nome", "pais_obse"]
        labels = {
            "pais_codi": "Código",
            "pais_nome": "Nome",
            "pais_obse": "Observações",
        }
        widgets = {
            "pais_codi": forms.NumberInput(attrs={"class": "form-control"}),
            "pais_nome": forms.TextInput(attrs={"class": "form-control"}),
            "pais_obse": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_pais_nome(self):
        return (self.cleaned_data.get("pais_nome") or "").strip()


class CidadesForm(forms.ModelForm):
    """
    O queryset de estado/país é definido pela view (multibanco),
    via `set_banco(banco)`.
    """

    class Meta:
        model = Cidades
        fields = ["cida_codi", "cida_nome", "cida_esta", "cida_pais", "cida_sigl", "cida_fret"]
        labels = {
            "cida_codi": "Código IBGE",
            "cida_nome": "Nome",
            "cida_esta": "Estado",
            "cida_pais": "País",
            "cida_sigl": "Sigla (UF)",
            "cida_fret": "Frete",
        }
        widgets = {
            "cida_codi": forms.NumberInput(attrs={"class": "form-control"}),
            "cida_nome": forms.TextInput(attrs={"class": "form-control"}),
            "cida_esta": forms.Select(attrs={"class": "form-select"}),
            "cida_pais": forms.Select(attrs={"class": "form-select"}),
            "cida_sigl": forms.TextInput(
                attrs={"class": "form-control text-uppercase", "maxlength": 2}
            ),
            "cida_fret": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def set_banco(self, banco):
        """Ajusta os querysets das FKs para o banco da licença."""
        self.fields["cida_esta"].queryset = (
            Estados.objects.using(banco).order_by("esta_nome")
        )
        self.fields["cida_pais"].queryset = (
            Paises.objects.using(banco).order_by("pais_nome")
        )

    def clean_cida_nome(self):
        return (self.cleaned_data.get("cida_nome") or "").strip()

    def clean_cida_sigl(self):
        return (self.cleaned_data.get("cida_sigl") or "").strip().upper()


class ImportarCidadeIBGEForm(forms.Form):
    """Form simples para importar uma cidade pelo código IBGE."""

    codigo_ibge = forms.IntegerField(
        label="Código IBGE do município",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Ex: 4119905 (Ponta Grossa)"}
        ),
    )
