# notas_fiscais/forms.py

from django import forms
from django.forms import inlineformset_factory
from ..models import Nota, NotaItem, NotaItemImposto, Transporte, NotaFatura, NotaDuplicata
from Entidades.models import Entidades
from Produtos.models import Produtos


NATUREZA_OPERACAO_CHOICES = [
    ("Venda de mercadoria", "Venda de mercadoria"),
    ("Venda de produção do estabelecimento", "Venda de produção do estabelecimento"),
    ("Devolução de venda", "Devolução de venda"),
    ("Remessa", "Remessa"),
]


class NotaForm(forms.ModelForm):
    natureza_operacao = forms.ChoiceField(
        choices=NATUREZA_OPERACAO_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="Venda de mercadoria",
        required=False,
    )
    destinatario = forms.ModelChoiceField(
        queryset=Entidades.objects.none(),
        widget=forms.Select(attrs={"class": "form-control select2"}),
        help_text="Cliente / Destinatário da nota"
    )

    class Meta:
        model = Nota
        fields = [
            "modelo", "serie", "numero",
            "data_emissao", "data_saida",
            "tipo_operacao", "finalidade", "ambiente",
            "destinatario",
            "informacoes_adicionais",
            "valor_total_tributos",
            "icms_uf_dest_valor_total",
        ]

        widgets = {
            "modelo": forms.Select(attrs={"class": "form-control"}),
            "data_emissao": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "data_saida": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "serie": forms.TextInput(attrs={"class": "form-control"}),
            "numero": forms.NumberInput(attrs={"class": "form-control"}),
            "tipo_operacao": forms.Select(attrs={"class": "form-control"}),
            "finalidade": forms.Select(attrs={"class": "form-control"}),
            "ambiente": forms.Select(attrs={"class": "form-control"}),
            "informacoes_adicionais": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "valor_total_tributos": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
            "icms_uf_dest_valor_total": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        database = kwargs.pop("database", "default")
        empresa_id = kwargs.pop("empresa_id", None)

        super().__init__(*args, **kwargs)

        if "numero" in self.fields:
            self.fields["numero"].required = False
        if "serie" in self.fields:
            self.fields["serie"].required = False

        if empresa_id:
            self.fields["destinatario"].queryset = Entidades.objects.using(database).filter(
                enti_empr=empresa_id,
                enti_tipo_enti__in=["CL", "AM"]
            )

    def clean_numero(self):
        v = self.cleaned_data.get("numero")
        if (v is None or v == "") and getattr(self.instance, "pk", None):
            return getattr(self.instance, "numero", None)
        return v

    def clean_serie(self):
        v = self.cleaned_data.get("serie")
        if (v is None or str(v).strip() == "") and getattr(self.instance, "pk", None):
            return getattr(self.instance, "serie", None)
        return v


class NotaItemForm(forms.ModelForm):
    produto = forms.ModelChoiceField(
        queryset=Produtos.objects.none(),
        required=False,
        widget=forms.HiddenInput(attrs={"class": "form-control"}),
    )
    class Meta:
        model = NotaItem
        fields = [
            "produto",
            "quantidade", "unitario", "desconto",   
            "cfop", "ncm", "cest",
            "cst_icms", "cst_pis", "cst_cofins",
            "cst_ibs", "cst_cbs",
            "numero_pedido", "numero_item_pedido",
            "informacoes_adicionais", "valor_total_tributos",
            "valor_frete", "valor_seguro", "valor_outras_despesas",
        ]
        widgets = {
            "quantidade": forms.NumberInput(attrs={"step": "0.0001", "class": "form-control"}),
            "unitario": forms.NumberInput(attrs={"step": "0.0001", "class": "form-control"}),
            "desconto": forms.NumberInput(attrs={"step": "0.0001", "class": "form-control"}),
            "cfop": forms.TextInput(attrs={"class": "form-control"}),
            "ncm": forms.TextInput(attrs={"class": "form-control"}),
            "cest": forms.TextInput(attrs={"class": "form-control"}),
            "cst_icms": forms.TextInput(attrs={"class": "form-control"}),
            "cst_pis": forms.TextInput(attrs={"class": "form-control"}),
            "cst_cofins": forms.TextInput(attrs={"class": "form-control"}),
            "cst_ibs": forms.TextInput(attrs={"class": "form-control"}),
            "cst_cbs": forms.TextInput(attrs={"class": "form-control"}),
            "numero_pedido": forms.TextInput(attrs={"class": "form-control"}),
            "numero_item_pedido": forms.NumberInput(attrs={"class": "form-control"}),
            "informacoes_adicionais": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "valor_total_tributos": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
            "valor_frete": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
            "valor_seguro": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
            "valor_outras_despesas": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        database = kwargs.pop("database", "default")
        empresa_id = kwargs.pop("empresa_id", None)
        super().__init__(*args, **kwargs)

        for f in ["cfop", "ncm", "cst_icms", "cst_pis", "cst_cofins", "cst_ibs", "cst_cbs", "cest"]:
            if f in self.fields:
                self.fields[f].required = False

        qs = Produtos.objects.using(database)
        if empresa_id is not None:
            qs = qs.filter(prod_empr=str(empresa_id))
        self.fields["produto"].queryset = qs

        if self.instance and self.instance.pk:
            self.fields["produto"].initial = self.instance.produto_id


# Formset de itens
NotaItemFormSet = inlineformset_factory(
    Nota,
    NotaItem,
    form=NotaItemForm,
    extra=0,
    can_delete=True
)



class NotaItemImpostoForm(forms.ModelForm):
    class Meta:
        model = NotaItemImposto
        fields = [
            "icms_base", "icms_aliquota", "icms_valor",
            "ipi_valor", "pis_valor", "cofins_valor",
            "fcp_valor",
            "ibs_base", "ibs_aliquota", "ibs_valor",
            "cbs_base", "cbs_aliquota", "cbs_valor",
            "icms_uf_dest_base", "icms_uf_dest_aliquota", "icms_uf_dest_valor",
            "icms_uf_dest_fcp_valor", "icms_uf_dest_partilha",
        ]
        widgets = {
            "icms_aliquota": forms.NumberInput(attrs={"step": "0.01"}),
            "ibs_aliquota": forms.NumberInput(attrs={"step": "0.01"}),
            "cbs_aliquota": forms.NumberInput(attrs={"step": "0.01"}),
            "icms_uf_dest_aliquota": forms.NumberInput(attrs={"step": "0.01"}),
            "icms_uf_dest_partilha": forms.NumberInput(attrs={"step": "0.01"}),
        }




class TransporteForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "transportadora" in self.fields:
            self.fields["transportadora"].required = False

    class Meta:
        model = Transporte
        fields = [
            "modalidade_frete",
            "transportadora",
            "placa_veiculo",
            "uf_veiculo",
        ]
        widgets = {
            "modalidade_frete": forms.Select(attrs={"class": "form-control"}),
            "transportadora": forms.TextInput(attrs={"class": "form-control"}),
            "placa_veiculo": forms.TextInput(attrs={"class": "form-control"}),
            "uf_veiculo": forms.TextInput(attrs={"class": "form-control"}),
        }


class NotaFaturaForm(forms.ModelForm):
    class Meta:
        model = NotaFatura
        fields = ["numero", "valor_original", "valor_desconto", "valor_liquido"]
        widgets = {
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "valor_original": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
            "valor_desconto": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
            "valor_liquido": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
        }


class NotaDuplicataForm(forms.ModelForm):
    class Meta:
        model = NotaDuplicata
        fields = ["ordem", "numero", "data_vencimento", "valor"]
        widgets = {
            "ordem": forms.NumberInput(attrs={"class": "form-control"}),
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "data_vencimento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "valor": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
        }


NotaDuplicataFormSet = inlineformset_factory(
    Nota,
    NotaDuplicata,
    form=NotaDuplicataForm,
    extra=0,
    can_delete=True,
)


class EnviarXmlContabilidadeForm(forms.Form):
    data_inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    data_fim = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    emails = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "email@dominio.com; outro@dominio.com"}),
        required=True,
    )


class EnviarNotaEmailForm(forms.Form):
    emails = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "email@dominio.com; outro@dominio.com"}),
        required=True,
    )
    assunto = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}), required=False)
    mensagem = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        required=False,
    )
    anexar_pdf = forms.BooleanField(required=False, initial=True)
    anexar_xml = forms.BooleanField(required=False, initial=True)

    def clean_emails(self):
        raw = (self.cleaned_data.get("emails") or "").strip()
        emails = [e.strip() for e in raw.replace(",", ";").split(";") if e.strip()]
        if not emails:
            raise forms.ValidationError("Informe ao menos um e-mail de destino.")
        for e in emails:
            try:
                forms.EmailField().clean(e)
            except forms.ValidationError:
                raise forms.ValidationError(f"E-mail inválido: {e}")
        return "; ".join(emails)
