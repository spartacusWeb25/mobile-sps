from django import forms
from django.forms import formset_factory
from Pisos.models import Pedidospisos, Orcamentopisos, PedidosPisosArquivos, StatusPisos



class StatusPisosForm(forms.ModelForm):
    class Meta:
        model = StatusPisos
        fields = [
            "stat_codigo",
            "stat_desc",
            "stat_tipo",
            "stat_ativo",
        ]

        widgets = {
            "stat_codigo": forms.NumberInput(attrs={"class": "form-control"}),
            "stat_desc": forms.TextInput(attrs={"class": "form-control"}),
            "stat_tipo": forms.Select(attrs={"class": "form-select"}),
            "stat_ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "stat_codigo": "Código",
            "stat_desc": "Descrição",
            "stat_tipo": "Tipo",
            "stat_ativo": "Ativo",
        }


PEDIDO_STATUS_CHOICES = (
    (0, "Aguardando Financeiro"),
    (1, "Aguardando Compras"),
    (2, "Compra Efetuada"),
    (3, "Material Disponível"),
    (4, "Logística"),
    (5, "Cancelado"),
    (6, "Concluído"),
)

class PedidoPisosForm(forms.ModelForm):
    class Meta:
        model = Pedidospisos
        fields = [
            "pedi_empr", "pedi_fili", "pedi_clie", "pedi_forn", "pedi_vend", "pedi_data",
            "pedi_data_prev_entr", "pedi_orca", "pedi_stat",
            "pedi_form_paga", "pedi_desc", "pedi_fret", "pedi_cred", "pedi_tota", "pedi_obse",
            "pedi_nome_reti", "pedi_espe_reti", "pedi_comp","pedi_ende", "pedi_nume_ende", "pedi_bair", "pedi_cida", "pedi_esta","pedi_obse_roma", 
            "pedi_croq_info","pedi_data_inst", "pedi_data_entr_inst", "pedi_mode_piso", "pedi_mode_alum", "pedi_mode_roda", "pedi_mode_port", "pedi_mode_outr",
            "pedi_sent_piso","pedi_sent_piso", "pedi_ajus_port", "pedi_degr_esca", "pedi_obra_habi", "pedi_movi_mobi","pedi_remo_roda", "pedi_remo_carp",
        ]
        widgets = {k: forms.DateInput(attrs={"type": "date", "class": "form-control"}) for k in [
            "pedi_data", "pedi_data_prev_entr", "pedi_data_inst", "pedi_data_entr_inst"
        ]}
        widgets["pedi_obse"] = forms.TextInput(attrs={"class": "form-control form-control-sm"})
        widgets["pedi_obse_roma"] = forms.TextInput(attrs={"class": "form-control form-control-sm"})        
        widgets["pedi_croq_info"] = forms.TextInput(attrs={"rows": 1, "class": "form-control"})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs.setdefault("class", css)
        if "pedi_stat" in self.fields:
            self.fields["pedi_stat"].widget = forms.Select(
                choices=[("", "Selecione")] + list(PEDIDO_STATUS_CHOICES),
                attrs={"class": "form-control status-select"},
            )
        if "pedi_tota" in self.fields:
            self.fields["pedi_tota"].widget.attrs.setdefault("readonly", True)
        if "pedi_cred" in self.fields:
            self.fields["pedi_cred"].widget.attrs.setdefault("readonly", True)

        if "pedi_form_paga" in self.fields:
            valor_inicial = self.initial.get(
                "pedi_form_paga",
                getattr(self.instance, "pedi_form_paga", None),
            )
            formas_pagamento = [
                ("", "Selecione"),
                (99, "SEM FINANCEIRO"),
                (0, "DUPLICATA"),
                (1, "CHEQUE"),
                (2, "PROMISSÓRIA"),
                (3, "RECIBO"),
                (50, "CHEQUE-PRÉ"),
                (51, "CARTÃO DE CRÉDITO"),
                (52, "CARTÃO DE DÉBITO"),
                (53, "BOLETO"),
                (54, "DINHEIRO"),
                (55, "DEPÓSITO EM CONTA"),
                (60, "PIX"),
            ]
            self.fields["pedi_form_paga"] = forms.TypedChoiceField(
                choices=formas_pagamento,
                required=False,
                coerce=lambda v: int(v) if v != "" else None,
                empty_value=None,
                widget=forms.Select(attrs={"class": "form-control"}),
            )
            self.fields["pedi_form_paga"].initial = valor_inicial

class ItemPedidoPisosForm(forms.Form):
    item_ambi = forms.IntegerField(required=False)
    item_nome_ambi = forms.CharField(required=False, max_length=100)
    item_prod = forms.CharField(required=False, max_length=20)
    item_prod_nome = forms.CharField(required=False, max_length=100)
    item_m2 = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_quan = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_kg = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_caix = forms.IntegerField(required=False)
    item_unit = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_suto = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_desc = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_queb = forms.DecimalField(required=False, decimal_places=2, max_digits=5)
    item_obse = forms.CharField(required=False, widget=forms.TextInput(attrs={"rows": 1}))


ItemPedidoPisosFormSet = formset_factory(ItemPedidoPisosForm, extra=0, can_delete=True)


class OrcamentoPisosForm(forms.ModelForm):
    class Meta:
        model = Orcamentopisos
        fields = [
            "orca_empr", "orca_fili", "orca_clie", "orca_vend", "orca_data",
            "orca_data_prev_entr", "orca_data_inst", "orca_data_entr_inst",
            "orca_desc", "orca_fret", "orca_cred", "orca_tota", "orca_obse", "orca_croq_info",
            "orca_mode_piso", "orca_mode_alum", "orca_mode_roda", "orca_mode_port", "orca_mode_outr",
            "orca_sent_piso", "orca_ajus_port", "orca_degr_esca", "orca_obra_habi", "orca_movi_mobi",
            "orca_remo_roda", "orca_remo_carp", "orca_stat",
        ]
        widgets = {
            **{k: forms.DateInput(attrs={"type": "date", "class": "form-control"}) for k in [
                "orca_data", "orca_data_prev_entr", "orca_data_inst", "orca_data_entr_inst"
            ]},
            "orca_obse": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "orca_croq_info": forms.TextInput(attrs={"rows": 1, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs.setdefault("class", css)
        if "orca_tota" in self.fields:
            self.fields["orca_tota"].widget.attrs.setdefault("readonly", True)
        if "orca_cred" in self.fields:
            self.fields["orca_cred"].widget.attrs.setdefault("readonly", True)


class ItemOrcamentoPisosForm(forms.Form):
    item_ambi = forms.IntegerField(required=False)
    item_nome_ambi = forms.CharField(required=False, max_length=100)
    item_prod = forms.CharField(required=False, max_length=20)
    item_m2 = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_quan = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_caix = forms.IntegerField(required=False)
    item_unit = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_suto = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_desc = forms.DecimalField(required=False, decimal_places=4, max_digits=15)
    item_queb = forms.DecimalField(required=False, decimal_places=2, max_digits=5)
    item_obse = forms.CharField(required=False, widget=forms.TextInput(attrs={"rows": 1}))
    item_prod_nome = forms.CharField(required=False, max_length=100)


ItemOrcamentoPisosFormSet = formset_factory(ItemOrcamentoPisosForm, extra=0, can_delete=True)


from django import forms
from Pisos.models import Pedidospisos


class WorkflowForm(forms.ModelForm):
    class Meta:
        model = Pedidospisos
        fields = [
            "pedi_desc_fina_work", "pedi_data_fina_work",
            "pedi_desc_comp_work", "pedi_data_comp_work",
            "pedi_desc_inst_work", "pedi_data_inst_work",
            "pedi_desc_ence_work", "pedi_data_ence_work",
        ]

        widgets = {
            "pedi_data_fina_work": forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
            "pedi_data_comp_work": forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
            "pedi_data_inst_work": forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
            "pedi_data_ence_work": forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),

            "pedi_desc_fina_work": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "pedi_desc_comp_work": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "pedi_desc_inst_work": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "pedi_desc_ence_work": forms.TextInput(attrs={"class": "form-control form-control-sm"})
        }
        labels = {
            "pedi_desc_fina_work": "Financeiro Ok",
            "pedi_data_fina_work": "Data Finananceiro Ok",
            "pedi_desc_comp_work": "Compra Efetuada Ok",
            "pedi_data_comp_work": "Data Compra Ok",
            "pedi_desc_inst_work": "Instalação Ok",
            "pedi_data_inst_work": "Data Instalação Ok",
            "pedi_desc_ence_work": "Encerramento Pedido",
            "pedi_data_ence_work": "Data Encerramento Pedido",
        }


class PedidosPisosArquivosForm(forms.ModelForm):
    arqu_arqu = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control form-control-sm"}),
        label="Arquivo",
    )

    class Meta:
        model = PedidosPisosArquivos
        fields = [
            "arqu_empr", "arqu_pedi", "arqu_nome_arqu", "arqu_cod_arqu",
        ]
        labels = {
            "arqu_empr": "Empresa",
            "arqu_pedi": "Pedido",

            "arqu_cod_arqu": "Código Arquivo",
        }
        widgets = {}
        
