from django import forms

from processos.models import Processo, ProcessoChecklistResposta
from Entidades.models import Entidades


class ProcessoTipoForm(forms.Form):
    nome = forms.CharField(
        max_length=120,
        label="Nome",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome do tipo"}),
    )
    codigo = forms.CharField(
        max_length=50,
        label="Código",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Código do tipo"}),
    )
    ativo = forms.BooleanField(required=False, initial=True, label="Ativo")


class ChecklistModeloForm(forms.Form):
    processo_tipo_id = forms.IntegerField(
        label="Tipo de processo",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )
    nome = forms.CharField(
        max_length=120,
        label="Nome do modelo",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome do modelo"}),
    )
    versao = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Versão",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )
    ativo = forms.BooleanField(required=False, initial=True, label="Ativo")


class ChecklistItemForm(forms.Form):
    checklist_modelo_id = forms.IntegerField(
        label="Modelo",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )
    ordem = forms.IntegerField(
        min_value=0,
        initial=0,
        label="Ordem",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
    )
    descricao = forms.CharField(
        max_length=255,
        label="Descrição",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Descrição do item"}),
    )
    obrigatorio = forms.BooleanField(required=False, initial=True, label="Obrigatório")


class ProcessoForm(forms.ModelForm):
    proc_clie_label = forms.CharField(
        required=False,
        label="Cliente",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Cliente (nome ou código)"}),
    )
    proc_clie = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Processo
        fields = ["proc_tipo", "proc_desc", "proc_clie"]
        labels = {"proc_tipo": "Tipo de processo", "proc_desc": "Descrição", "proc_clie": "Cliente"}
        widgets = {
            "proc_tipo": forms.Select(attrs={"class": "form-select"}),
            "proc_desc": forms.TextInput(attrs={"class": "form-control", "placeholder": "Descreva o processo"}),
        }

    def __init__(self, *args, **kwargs):
        tipos = kwargs.pop("tipos", None)
        self.db_alias = kwargs.pop("db_alias", None)
        self.empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        if tipos is not None:
            self.fields["proc_tipo"].queryset = tipos
        self.fields["proc_clie"].required = False

        if getattr(self.instance, "proc_clie", None):
            try:
                ent = (
                    Entidades.objects.using(self.db_alias or "default")
                    .filter(
                        enti_empr=(self.empresa if self.empresa is not None else 1),
                        enti_clie=self.instance.proc_clie,
                    )
                    .first()
                )
                if ent:
                    self.initial["proc_clie_label"] = ent.enti_nome
                    self.initial["proc_clie"] = int(ent.enti_clie)
                else:
                    self.initial["proc_clie"] = int(self.instance.proc_clie)
            except Exception:
                pass
            except Exception:
                self.initial["proc_clie"] = getattr(self.instance, "proc_clie", None)

    def clean_proc_clie(self):
        val = self.cleaned_data.get("proc_clie")
        if val:
            try:
                return int(val)
            except Exception:
                return val

        raw = (self.cleaned_data.get("proc_clie_label") or "").strip()
        if not raw:
            return None
        if raw.isdigit():
            return int(raw)

        db_alias = self.db_alias or "default"
        empresa = self.empresa if self.empresa is not None else 1
        ent = (
            Entidades.objects.using(db_alias)
            .filter(enti_empr=empresa, enti_nome__icontains=raw)
            .order_by("enti_nome")
            .first()
        )
        if ent:
            return int(ent.enti_clie)
        raise forms.ValidationError("Cliente não encontrado. Informe o código ou selecione no autocomplete.")


class ProcessoRespostaInlineForm(forms.Form):
    item_id = forms.IntegerField(widget=forms.HiddenInput)
    resposta = forms.ChoiceField(
        required=False,
        choices=ProcessoChecklistResposta.RESPOSTA_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    observacao = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Observações"}),
    )


class ProcessoClienteForm(forms.Form):
    proc_clie_label = forms.CharField(
        required=False,
        label="Cliente",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Cliente (nome ou código)"}),
    )
    proc_clie = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        self.db_alias = kwargs.pop("db_alias", None)
        self.empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)

    def clean_proc_clie(self):
        val = self.cleaned_data.get("proc_clie")
        if val:
            try:
                return int(val)
            except Exception:
                return val

        raw = (self.cleaned_data.get("proc_clie_label") or "").strip()
        if not raw:
            return None
        if raw.isdigit():
            return int(raw)
        db_alias = self.db_alias or "default"
        empresa = self.empresa if self.empresa is not None else 1
        ent = (
            Entidades.objects.using(db_alias)
            .filter(enti_empr=empresa, enti_nome__icontains=raw)
            .order_by("enti_nome")
            .first()
        )
        if ent:
            return int(ent.enti_clie)
        raise forms.ValidationError("Cliente não encontrado. Informe o código ou selecione no autocomplete.")
