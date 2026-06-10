# notas_fiscais/serializers.py

from rest_framework import serializers
from ..models import (
    Nota, NotaItem, NotaItemImposto, NotaFatura, NotaDuplicata,
    Transporte
)
from Entidades.models import Entidades
from Licencas.models import Filiais


# ============================================================
# PARTICIPANTES (LEITURA)
# ============================================================

class DestinatarioResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entidades
        fields = ["enti_clie", "enti_nome", "enti_cnpj", "enti_cpf", "enti_emai"]


class EmitenteResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filiais
        fields = ["empr_empr", "empr_codi", "empr_nome", "empr_docu", "empr_cep", "empr_ende", "empr_cida", "empr_esta"]


# ============================================================
# ITENS + IMPOSTOS (LEITURA)
# ============================================================

class NotaItemImpostoSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotaItemImposto
        fields = "__all__"


class NotaItemSerializer(serializers.ModelSerializer):
    impostos = NotaItemImpostoSerializer(read_only=True)
    produto_nome = serializers.SerializerMethodField()

    class Meta:
        model = NotaItem
        fields = "__all__"

    def get_produto_nome(self, obj):
        try:
            # Acessar obj.produto dispara query sem filtro de empresa (causa erro MultipleObjectsReturned)
            # Precisamos filtrar pela empresa da nota
            from Produtos.models import Produtos
            prod_id = obj.produto_id
            empresa = obj.nota.empresa
            p = Produtos.objects.filter(prod_codi=prod_id, prod_empr=empresa).first()
            return p.prod_nome if p else None
        except Exception:
            return None


# ============================================================
# TRANSPORTE (LEITURA)
# ============================================================

class TransporteSerializer(serializers.ModelSerializer):
    transportadora_nome = serializers.SerializerMethodField()
    class Meta:
        model = Transporte
        fields = "__all__"

    def get_transportadora_nome(self, obj):
        if not obj.transportadora_id:
            return None
        request = self.context.get("request") if hasattr(self, "context") else None
        from core.utils import get_licenca_db_config
        banco = get_licenca_db_config(request) if request is not None else obj._state.db or "default"
        from Entidades.models import Entidades
        row = (
            Entidades.objects.using(banco)
            .filter(enti_clie=obj.transportadora_id)
            .values("enti_nome")
            .first()
        )
        return row.get("enti_nome") if row else None


class NotaDuplicataSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotaDuplicata
        fields = "__all__"


class NotaFaturaSerializer(serializers.ModelSerializer):
    duplicatas = NotaDuplicataSerializer(many=True, read_only=True)

    class Meta:
        model = NotaFatura
        fields = "__all__"


# ============================================================
# NOTA – LEITURA
# ============================================================

class NotaDetailSerializer(serializers.ModelSerializer):
    itens = NotaItemSerializer(many=True, read_only=True)
    transporte = TransporteSerializer(read_only=True)
    fatura = serializers.SerializerMethodField()
    duplicatas = serializers.SerializerMethodField()
    emitente = serializers.SerializerMethodField()
    destinatario = serializers.SerializerMethodField()

    class Meta:
        model = Nota
        fields = "__all__"

    def get_emitente(self, obj):
        request = self.context.get("request") if hasattr(self, "context") else None
        from core.utils import get_licenca_db_config
        banco = get_licenca_db_config(request) if request is not None else obj._state.db or "default"
        data = (
            Filiais.objects.using(banco)
            .filter(empr_empr=obj.empresa, empr_codi=obj.filial)
            .values("empr_empr", "empr_codi", "empr_nome", "empr_docu", "empr_cep", "empr_ende", "empr_cida", "empr_esta")
            .first()
        )
        return data

    def get_destinatario(self, obj):
        request = self.context.get("request") if hasattr(self, "context") else None
        from core.utils import get_licenca_db_config
        banco = get_licenca_db_config(request) if request is not None else obj._state.db or "default"
        data = (
            Entidades.objects.using(banco)
            .filter(enti_empr=obj.empresa, enti_clie=obj.destinatario_id)
            .values("enti_clie", "enti_nome", "enti_cnpj", "enti_cpf", "enti_emai")
            .first()
        )
        return data

    def get_fatura(self, obj):
        try:
            fatura = getattr(obj, "fatura", None)
            if not fatura:
                return None
            return NotaFaturaSerializer(fatura).data
        except Exception:
            return None

    def get_duplicatas(self, obj):
        try:
            qs = obj.duplicatas.all()
            return NotaDuplicataSerializer(qs, many=True).data
        except Exception:
            return []


# ============================================================
# NOTA – ESCRITA (API)
# ============================================================

class NotaItemCreateSerializer(serializers.Serializer):
    produto = serializers.CharField()
    quantidade = serializers.DecimalField(max_digits=15, decimal_places=4)
    unitario = serializers.DecimalField(max_digits=15, decimal_places=4)
    desconto = serializers.DecimalField(max_digits=15, decimal_places=4, required=False, default=0)
    valor_frete = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    valor_seguro = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    valor_outras_despesas = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    cfop = serializers.CharField(required=False, allow_blank=True, default="")
    ncm = serializers.CharField(required=False, allow_blank=True, default="")
    cest = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    cst_icms = serializers.CharField(required=False, allow_blank=True, default="")
    cst_pis = serializers.CharField(required=False, allow_blank=True, default="")
    cst_cofins = serializers.CharField(required=False, allow_blank=True, default="")
    cst_ibs = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cst_cbs = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    numero_pedido = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    numero_item_pedido = serializers.IntegerField(required=False, allow_null=True)
    informacoes_adicionais = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    valor_total_tributos = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)


class NotaItemImpostoCreateSerializer(serializers.Serializer):
    icms_base = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    icms_aliquota = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    icms_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    ipi_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    pis_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    cofins_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    fcp_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    ibs_base = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    ibs_aliquota = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    ibs_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    cbs_base = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    cbs_aliquota = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    cbs_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    icms_uf_dest_base = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    icms_uf_dest_aliquota = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    icms_uf_dest_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    icms_uf_dest_fcp_valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    icms_uf_dest_partilha = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)


class NotaFaturaCreateSerializer(serializers.Serializer):
    numero = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    valor_original = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    valor_desconto = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    valor_liquido = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)


class NotaDuplicataCreateSerializer(serializers.Serializer):
    ordem = serializers.IntegerField(required=False, allow_null=True)
    numero = serializers.CharField()
    data_vencimento = serializers.DateField(required=False, allow_null=True)
    valor = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)


class TransporteCreateSerializer(serializers.Serializer):
    modalidade_frete = serializers.IntegerField()
    transportadora = serializers.IntegerField(required=False, allow_null=True)
    placa_veiculo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    uf_veiculo = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class NotaCreateUpdateSerializer(serializers.Serializer):
    modelo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    serie = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    numero = serializers.IntegerField(required=False, allow_null=True)
    pedido_origem = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    chave_referenciada = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    data_emissao = serializers.DateField(required=False)
    data_saida = serializers.DateField(required=False, allow_null=True)

    tipo_operacao = serializers.IntegerField()
    finalidade = serializers.IntegerField(required=False)
    ambiente = serializers.IntegerField(required=False)
    informacoes_adicionais = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    valor_total_tributos = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    icms_uf_dest_valor_total = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)

    destinatario = serializers.IntegerField()  # enti_clie

    itens = NotaItemCreateSerializer(many=True)
    impostos = NotaItemImpostoCreateSerializer(many=True, required=False)
    transporte = TransporteCreateSerializer(required=False)
    fatura = NotaFaturaCreateSerializer(required=False)
    duplicatas = NotaDuplicataCreateSerializer(many=True, required=False)

    def validate(self, attrs):
        itens = list(attrs.get("itens") or [])
        impostos = list(attrs.get("impostos") or [])

        itens_filtrados = []
        impostos_filtrados = []
        for idx, item in enumerate(itens):
            produto = str(item.get("produto") or "").strip()
            if not produto or produto == "0":
                continue
            itens_filtrados.append(item)
            if idx < len(impostos):
                impostos_filtrados.append(impostos[idx])

        attrs["itens"] = itens_filtrados
        if impostos:
            attrs["impostos"] = impostos_filtrados

        itens = attrs.get("itens") or []
        impostos = attrs.get("impostos") or []

        if not itens:
            raise serializers.ValidationError("A nota precisa ter pelo menos um item.")

        if impostos and len(impostos) != len(itens):
            raise serializers.ValidationError("Se enviados, impostos devem ter o mesmo tamanho da lista de itens.")

        return attrs


class EnviarXmlContabilidadeSerializer(serializers.Serializer):
    data_inicio = serializers.DateField()
    data_fim = serializers.DateField()
    emails = serializers.ListField(child=serializers.EmailField(), required=False)
    email = serializers.EmailField(required=False)
    incluir_pastas = serializers.BooleanField(required=False, default=True)
    status_list = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, attrs):
        data_inicio = attrs.get("data_inicio")
        data_fim = attrs.get("data_fim")
        if data_inicio and data_fim and data_inicio > data_fim:
            raise serializers.ValidationError("Data início não pode ser maior que data fim.")

        emails = attrs.get("emails") or []
        email = attrs.get("email")
        if email:
            emails = list(emails) + [email]
        if not emails:
            raise serializers.ValidationError("Informe ao menos um e-mail de destino.")
        attrs["emails"] = emails
        return attrs
