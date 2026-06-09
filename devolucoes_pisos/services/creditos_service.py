from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import CharField
from django.db.models.functions import Cast
from Licencas.models import Empresas, Filiais
from Entidades.models import Entidades
from devolucoes_pisos.models import Creditotrocas
from core.utils import get_db_from_slug


class DadosService:
    @staticmethod
    def listar_empresas(*, banco):
        return (
            Empresas.objects.using(banco)
            .all()
            .order_by("empr_codi")
        )

    @staticmethod
    def listar_filiais(*, banco, empresa):
        return (
            Filiais.objects.using(banco)
            .filter(empr_empr=empresa)
            .order_by("empr_codi")
        )
    
    @staticmethod
    def mapa_clientes(*, banco):
        clientes = (
            Entidades.objects.using(banco)
            .all()
            .values("enti_clie", "enti_nome")
        )

        return {
            c["enti_clie"]: c["enti_nome"]
            for c in clientes
        }


class CreditosService:

    @staticmethod
    def listar(*, banco, empresa, filial):
        rows = list(
            Creditotrocas.objects.using(banco)
            .filter(
                cred_fina_empr=empresa,
                cred_fina_fili=filial,
            )
            .annotate(cred_fina_data_txt=Cast("cred_fina_data", output_field=CharField()))
            .values(
                "cred_id",
                "cred_fina_clie",
                "cred_fina_vend",
                "cred_fina_data_txt",
                "cred_fina_es",
                "cred_fina_valo",
                "cred_fina_obse",
            )
            .order_by("-cred_fina_data", "-cred_id")
        )

        mapa_clientes = DadosService.mapa_clientes(banco=banco)
        creditos = []

        for row in rows:
            credito = type("CreditoRow", (), {})()
            credito.cred_id = row.get("cred_id")
            credito.pk = credito.cred_id
            credito.cred_fina_clie = row.get("cred_fina_clie")
            credito.cred_fina_vend = row.get("cred_fina_vend")
            credito.cred_fina_es = row.get("cred_fina_es")
            credito.cred_fina_valo = row.get("cred_fina_valo")
            credito.cred_fina_obse = row.get("cred_fina_obse")
            credito.cred_fina_data = row.get("cred_fina_data_txt")
            credito.cliente_nome = mapa_clientes.get(credito.cred_fina_clie)
            creditos.append(credito)

        return creditos

    @staticmethod
    def buscar_por_id(*, banco, empresa, filial, credito_id):
        return (
            Creditotrocas.objects.using(banco)
            .filter(
                cred_fina_empr=empresa,
                cred_fina_fili=filial,
                cred_id=credito_id,
            )
            .first()
        )

    @staticmethod
    def transferir_entre_empresa_filial(
        *,
        banco,
        credito_id,
        empresa_origem,
        filial_origem,
        empresa_destino,
        filial_destino,
        observacao=None,
    ):
        banco = get_db_from_slug(banco)
        with transaction.atomic(using=banco):
            credito = CreditosService.buscar_por_id(
                banco=banco,
                empresa=empresa_origem,
                filial=filial_origem,
                credito_id=credito_id,
            )

            if not credito:
                raise ValueError("Crédito não encontrado na empresa/filial de origem.")

            credito.cred_fina_empr = int(empresa_destino)
            credito.cred_fina_fili = int(filial_destino)
            credito.cred_fina_obse = observacao or (
                f"Transferido da empresa {empresa_origem}, filial {filial_origem}"
            )

            credito.save(
                using=banco,
                update_fields=[
                    "cred_fina_empr",
                    "cred_fina_fili",
                    "cred_fina_obse",
                ],
            )

            return credito
