from django import forms

from Entidades.models import Entidades
from processos.models import Processo, ProcessoChecklistResposta, ChecklistModelo

import logging
logger = logging.getLogger(__name__)


class ChecklistModeloForm(forms.Form):
    nome = forms.CharField(
        max_length=120,
        label="Nome do modelo",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome do modelo"}),
    )
    ativo = forms.BooleanField(required=False, initial=True, label="Ativo")


class ProcessoForm(forms.ModelForm):

    class Meta:
        model = Processo
        fields = ["proc_os", "proc_mode", "proc_desc"]
        labels = {"proc_os" : "Ordem de serviço", "proc_mode": "Modelo de processo", "proc_desc": "Descrição"}
        widgets = {
            "proc_os": forms.Select(attrs={"class": "form-select", "id": "os_input"}),
            "proc_mode": forms.Select(attrs={"class": "form-select", "id": "modelo_input"}),
            "proc_desc": forms.TextInput(attrs={"class": "form-control", "placeholder": "Descreva o processo (Opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        os = kwargs.pop("os", None)
        modelos = kwargs.pop("modelos", None)
        self.db_alias = kwargs.pop("db_alias", None)
        self.empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        self.fields['proc_mode'].queryset = ChecklistModelo.objects.none()
        if modelos is not None:
            self.fields["proc_mode"].queryset = modelos
        if os is not None:
            self.fields["proc_os"].queryset = os
            self.os_cliente_map = {
                str(obj.pk): obj.clie_nome for obj in os
            }
        else:
            self.os_cliente_map = {}
        self.fields["proc_mode"].label_from_instance = lambda obj: f"{obj.chmo_nome}"
        self.fields["proc_os"].label_from_instance = lambda obj: f"{obj.os_os} - ({obj.os_data_aber.strftime('%d/%m/%Y')}) - {obj.clie_nome}"
        self.fields['proc_os'].empty_label = "Selecione uma OS"


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

class ProcessoResponsavelForm(forms.Form):
    responsavel = forms.ModelChoiceField(
        label="Responsável",
        queryset=Entidades.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    documento = forms.CharField(
        required=True,
        max_length=255,
        label="Documento (CPF / Matrícula)",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "000.000.000-00"}),
    )
    def __init__(self, *args, **kwargs):
        self.db_alias = kwargs.pop("db_alias", None)
        self.empresa = kwargs.pop("empresa", None)
        entidades = kwargs.pop("entidades", None)
        super().__init__(*args, **kwargs)
        if entidades is not None:
            self.fields["responsavel"].queryset = entidades
        self.fields["responsavel"].label_from_instance = lambda obj: f"{obj.enti_nome}"
        self.fields["responsavel"].empty_label = "Selecione o responsável"