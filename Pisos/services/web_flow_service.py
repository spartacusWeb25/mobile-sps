from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.db import transaction

from Pisos.models import Pedidospisos
from Pisos.serializers import PedidospisosSerializer, OrcamentopisosSerializer
from Pisos.services.calculo_services import recomputar_total_pedido


def _get_empresa_filial_from_request(request):
    if request is None:
        return None, None

    empresa = (
        getattr(request, "empresa", None)
        or getattr(getattr(request, "session", None), "get", lambda *_: None)("empresa_id")
        or request.headers.get("X-Empresa")
    )
    filial = (
        getattr(request, "filial", None)
        or getattr(getattr(request, "session", None), "get", lambda *_: None)("filial_id")
        or request.headers.get("X-Filial")
    )

    if empresa in (None, "") or filial in (None, ""):
        return None, None

    try:
        empresa = int(empresa)
    except Exception:
        pass
    try:
        filial = int(filial)
    except Exception:
        pass

    return empresa, filial


class PedidoPisosWebFlowService:
    @staticmethod
    def criar(banco, payload, request=None):
        serializer = PedidospisosSerializer(data=payload, context={"banco": banco, "request": request})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    @staticmethod
    def atualizar(banco, pedido_nume, payload, request=None):
        empresa, filial = _get_empresa_filial_from_request(request)
        if empresa is None or filial is None:
            raise DRFValidationError("Empresa e filial são obrigatórias para atualizar pedido de pisos.")

        inst = Pedidospisos.objects.using(banco).get(
            pedi_empr=empresa,
            pedi_fili=filial,
            pedi_nume=pedido_nume,
        )
        serializer = PedidospisosSerializer(inst, data=payload, partial=False, context={"banco": banco, "request": request})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    @staticmethod
    def normalizar_erro(exc):
        if isinstance(exc, (DRFValidationError, DjangoValidationError)):
            return getattr(exc, "detail", None) or getattr(exc, "message_dict", None) or str(exc)
        return str(exc)


from Pisos.models import Orcamentopisos, Itensorcapisos, Itenspedidospisos

def exportar_orcamento_para_pedido(banco, empresa, filial, numero):
    with transaction.atomic(using=banco):
        orcamento = (
            Orcamentopisos.objects.using(banco)
            .select_for_update()
            .get(orca_empr=empresa, orca_fili=filial, orca_nume=numero)
        )
        if orcamento.orca_stat == 2:
            raise ValueError("Orçamento já exportado")

        ultimo = (
            Pedidospisos.objects.using(banco)
            .select_for_update()
            .filter(pedi_empr=empresa, pedi_fili=filial)
            .order_by("-pedi_nume")
            .first()
        )
        prox = (ultimo.pedi_nume + 1) if ultimo else 1

        dados_pedido = {
            "pedi_empr": orcamento.orca_empr,
            "pedi_fili": orcamento.orca_fili,
            "pedi_nume": prox,
            "pedi_clie": orcamento.orca_clie,
            "pedi_data": orcamento.orca_data,
            "pedi_tota": 0,
            "pedi_obse": orcamento.orca_obse,
            "pedi_vend": orcamento.orca_vend,
            "pedi_desc": orcamento.orca_desc,
            "pedi_fret": orcamento.orca_fret,
            "pedi_cred": orcamento.orca_cred,
            "pedi_ende": orcamento.orca_ende,
            "pedi_nume_ende": orcamento.orca_nume_ende,
            "pedi_comp": orcamento.orca_comp,
            "pedi_bair": orcamento.orca_bair,
            "pedi_cida": orcamento.orca_cida,
            "pedi_esta": orcamento.orca_esta,
            "pedi_orca": orcamento.orca_nume,
            "pedi_mode_piso": orcamento.orca_mode_piso,
            "pedi_mode_alum": orcamento.orca_mode_alum,
            "pedi_mode_roda": orcamento.orca_mode_roda,
            "pedi_mode_port": orcamento.orca_mode_port,
            "pedi_mode_outr": orcamento.orca_mode_outr,
            "pedi_sent_piso": orcamento.orca_sent_piso,
            "pedi_ajus_port": orcamento.orca_ajus_port,
            "pedi_degr_esca": orcamento.orca_degr_esca,
            "pedi_obra_habi": orcamento.orca_obra_habi,
            "pedi_movi_mobi": orcamento.orca_movi_mobi,
            "pedi_remo_roda": orcamento.orca_remo_roda,
            "pedi_remo_carp": orcamento.orca_remo_carp,
            "pedi_croq_info": orcamento.orca_croq_info,
            "pedi_stat": 0,
        }

        pedido = Pedidospisos.objects.using(banco).create(**dados_pedido)
        for idx, i in enumerate(
            Itensorcapisos.objects.using(banco)
            .filter(item_empr=empresa, item_fili=filial, item_orca=numero)
            .order_by("item_ambi", "item_nume"),
            start=1,
        ):
            item_nume = getattr(i, "item_nume", None)
            if item_nume in (None, "", 0, "0"):
                item_nume = idx

            item_ambi = getattr(i, "item_ambi", None)
            if item_ambi in (None, "", 0, "0"):
                item_ambi = idx

            Itenspedidospisos.objects.using(banco).create(
                item_empr=pedido.pedi_empr,
                item_fili=pedido.pedi_fili,
                item_pedi=pedido.pedi_nume,
                item_ambi=item_ambi,
                item_prod=i.item_prod,
                item_m2=i.item_m2,
                item_quan=i.item_quan,
                item_unit=i.item_unit,
                item_suto=i.item_suto,
                item_obse=i.item_obse,
                item_nome_ambi=i.item_nome_ambi,
                item_nume=item_nume,
                item_caix=i.item_caix,
                item_desc=i.item_desc,
                item_queb=i.item_queb,
            )
        recomputar_total_pedido(banco, pedido)
        Orcamentopisos.objects.using(banco).filter(
            orca_empr=empresa,
            orca_fili=filial,
            orca_nume=numero,
        ).update(
            orca_stat=2,
            orca_pedi=pedido.pedi_nume,
        )

        return pedido.pedi_nume


class OrcamentoPisosWebFlowService:
    @staticmethod
    def criar(banco, payload, request=None):
        serializer = OrcamentopisosSerializer(data=payload, context={"banco": banco, "request": request})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    @staticmethod
    def atualizar(banco, orcamento_nume, payload, request=None):
        empresa, filial = _get_empresa_filial_from_request(request)
        if empresa is None or filial is None:
            raise DRFValidationError("Empresa e filial são obrigatórias para atualizar orçamento de pisos.")

        inst = Orcamentopisos.objects.using(banco).get(
            orca_empr=empresa,
            orca_fili=filial,
            orca_nume=orcamento_nume,
        )
        serializer = OrcamentopisosSerializer(inst, data=payload, partial=False, context={"banco": banco, "request": request})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    @staticmethod
    def normalizar_erro(exc):
        if isinstance(exc, (DRFValidationError, DjangoValidationError)):
            return getattr(exc, "detail", None) or getattr(exc, "message_dict", None) or str(exc)
        return str(exc)

