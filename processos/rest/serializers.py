from rest_framework import serializers

from Entidades.serializers import EntidadesSerializer
from O_S.REST.serializers import Base64BinaryField, OsSerializer
from O_S.models import Os
from processos.models import (
    ChecklistItem,
    ChecklistModelo,
    Processo,
    ProcessoChecklistResposta,
)

class ChecklistItemSerializer(serializers.ModelSerializer):
    empresa = serializers.IntegerField(source="chit_empr", read_only=True)
    filial = serializers.IntegerField(source="chit_fili", read_only=True)
    checklist_modelo_id = serializers.IntegerField(source="chit_mode_id", required=False)
    checklist_modelo_nome = serializers.CharField(
        source="chit_mode.chmo_nome", read_only=True
    )
    descricao = serializers.CharField(source="chit_desc")
    obrigatorio = serializers.BooleanField(source="chit_obri")

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

class ChecklistModeloSerializer(serializers.ModelSerializer):
    empresa = serializers.IntegerField(source="chmo_empr", read_only=True)
    filial = serializers.IntegerField(source="chmo_fili", read_only=True)
    nome = serializers.CharField(source="chmo_nome")
    ativo = serializers.BooleanField(source="chmo_ativ", required=False)
    itens = ChecklistItemSerializer(many=True)

    class Meta:
        model = ChecklistModelo
        fields = [
            "id",
            "empresa",
            "filial",
            "nome",
            "ativo",
            "itens"
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
    versao = serializers.IntegerField(source="pchr_vers", read_only=True)

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
            "versao"
        ]


class ProcessoReadSerializer(serializers.ModelSerializer):
    empresa = serializers.IntegerField(source="proc_empr", read_only=True)
    filial = serializers.IntegerField(source="proc_fili", read_only=True)
    modelo_id = serializers.IntegerField(source="proc_mode_id")
    modelo_nome = serializers.CharField(source="proc_mode.chmo_nome", read_only=True)
    descricao = serializers.CharField(source="proc_desc", required=False, allow_null=True, allow_blank=True, default=None)
    status = serializers.CharField(source="proc_stat", read_only=True)
    respostas = ProcessoChecklistRespostaSerializer(many=True, read_only=True)
    os = OsSerializer(source="proc_os", required=False, read_only=True, allow_null=True)
    data_abertura = serializers.DateTimeField(source="proc_data_aber", read_only=True)
    data_fechamento = serializers.DateTimeField(source="proc_data_fech", read_only=True)
    versao = serializers.IntegerField(source="proc_vers", read_only=True)
    responsavel_id = serializers.IntegerField(source="proc_enti_vali", required=False, allow_null=True, default=None)
    responsavel_nome = serializers.CharField(source="proc_enti_vali.enti_nome", read_only=True)
    assinatura_responsavel = Base64BinaryField(source="proc_enti_assi", required=False, allow_null=True)

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
            "os",
            "versao",
            "responsavel_id",
            "responsavel_nome",
            "assinatura_responsavel"
        ]

class ProcessoWriteSerializer(serializers.ModelSerializer):
    modelo_id = serializers.IntegerField(source="proc_mode_id")
    descricao = serializers.CharField(source="proc_desc", required=False, allow_null=True, allow_blank=True, default=None)
    os_id = serializers.PrimaryKeyRelatedField(
            source="proc_os",
            queryset=Os.objects.all(),
            write_only=True
        )
    responsavel_id = serializers.IntegerField(source="proc_enti_vali", required=False, allow_null=True, default=None)
    assinatura_responsavel = Base64BinaryField(source="proc_enti_assi", required=False, allow_null=True)

    class Meta:
        model = Processo
        fields = [
            "id",
            "modelo_id",
            "descricao",
            "os_id",
            "responsavel_id",
            "assinatura_responsavel"
        ]
