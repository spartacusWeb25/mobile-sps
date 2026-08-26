from rest_framework import serializers

from processos.models import (
    ChecklistItem,
    ChecklistModelo,
    Processo,
    ProcessoChecklistResposta,
)


class ChecklistModeloSerializer(serializers.ModelSerializer):
    empresa = serializers.IntegerField(source="chmo_empr", read_only=True)
    filial = serializers.IntegerField(source="chmo_fili", read_only=True)
    nome = serializers.CharField(source="chmo_nome")
    ativo = serializers.BooleanField(source="chmo_ativ", required=False)

    class Meta:
        model = ChecklistModelo
        fields = [
            "id",
            "empresa",
            "filial",
            "nome",
            "ativo",
        ]


class ChecklistItemSerializer(serializers.ModelSerializer):
    empresa = serializers.IntegerField(source="chit_empr", read_only=True)
    filial = serializers.IntegerField(source="chit_fili", read_only=True)
    checklist_modelo_id = serializers.IntegerField(source="chit_mode_id")
    checklist_modelo_nome = serializers.CharField(
        source="chit_mode.chmo_nome", read_only=True
    )
    descricao = serializers.CharField(source="chit_desc")
    obrigatorio = serializers.BooleanField(source="chit_obri", required=False)

    class Meta:
        model = ChecklistItem
        fields = [
            "id",
            "empresa",
            "filial",
            "checklist_modelo_id",
            "checklist_modelo_nome",
            "descricao",
            "obrigatorio",
        ]


class ProcessoChecklistRespostaSerializer(serializers.ModelSerializer):
    empresa = serializers.IntegerField(source="pchr_empr", read_only=True)
    filial = serializers.IntegerField(source="pchr_fili", read_only=True)
    processo_id = serializers.IntegerField(source="pchr_proc_id", read_only=True)
    item_id = serializers.IntegerField(source="pchr_item_id")
    item_descricao = serializers.CharField(source="pchr_item.chit_desc", read_only=True)
    item_obrigatorio = serializers.BooleanField(
        source="pchr_item.chit_obri", read_only=True
    )
    resposta = serializers.ChoiceField(
        source="pchr_resp",
        choices=ProcessoChecklistResposta.RESPOSTA_CHOICES,
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    observacao = serializers.CharField(
        source="pchr_obse", allow_blank=True, allow_null=True, required=False
    )
    validado = serializers.BooleanField(source="pchr_vali", read_only=True)
    data_validacao = serializers.DateTimeField(source="pchr_data_vali", read_only=True)

    class Meta:
        model = ProcessoChecklistResposta
        fields = [
            "id",
            "empresa",
            "filial",
            "processo_id",
            "item_id",
            "item_descricao",
            "item_obrigatorio",
            "resposta",
            "observacao",
            "validado",
            "data_validacao",
        ]


class ProcessoSerializer(serializers.ModelSerializer):
    empresa = serializers.IntegerField(source="proc_empr", read_only=True)
    filial = serializers.IntegerField(source="proc_fili", read_only=True)
    modelo_id = serializers.IntegerField(source="proc_mode_id")
    modelo_nome = serializers.CharField(source="proc_mode.chmo_nome", read_only=True)
    descricao = serializers.CharField(source="proc_desc")
    status = serializers.CharField(source="proc_stat", read_only=True)
    respostas = ProcessoChecklistRespostaSerializer(many=True, read_only=True)
    data_abertura = serializers.DateTimeField(source="proc_data_aber", read_only=True)
    data_fechamento = serializers.DateTimeField(source="proc_data_fech", read_only=True)

    class Meta:
        model = Processo
        fields = [
            "id",
            "empresa",
            "filial",
            "modelo_id",
            "modelo_nome",
            "descricao",
            "status",
            "respostas",
            "data_abertura",
            "data_fechamento",
        ]
