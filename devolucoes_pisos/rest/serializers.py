from rest_framework import serializers

from devolucoes_pisos.models import Devolucoespedidopiso, Itensdevolucoespisos


class ItensDevolucaoPisosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Itensdevolucoespisos
        fields = [
            "item_ambi",
            "item_prod",
            "item_m2",
            "item_quan",
            "item_unit",
            "item_desc",
            "item_suto",
            "item_obse",
            "item_nome_ambi",
            "item_prod_nome",
            "item_queb",
        ]


class DevolucaoPisosSerializer(serializers.ModelSerializer):
    itens = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)
    tipo = serializers.ChoiceField(choices=[("DEVO", "Devolução"), ("TROC", "Troca")], write_only=True, required=False)

    class Meta:
        model = Devolucoespedidopiso
        fields = [
            "devo_empr",
            "devo_fili",
            "devo_pedi",
            "devo_data",
            "devo_usua",
            "devo_desc",
            "devo_cred",
            "itens",
            "tipo",
        ]
        read_only_fields = ["devo_empr", "devo_fili", "devo_cred"]
