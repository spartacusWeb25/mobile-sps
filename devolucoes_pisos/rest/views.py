from rest_framework import status, viewsets
from rest_framework.response import Response

from core.utils import get_licenca_db_config
from devolucoes_pisos.rest.serializers import DevolucaoPisosSerializer
from devolucoes_pisos.services.troca_devolucao_service import DevolucaoPedidoPisoService


class DevolucaoPisosViewSet(viewsets.ModelViewSet):
    serializer_class = DevolucaoPisosSerializer
    lookup_field = "devo_pedi"

    def get_queryset(self):
        banco = get_licenca_db_config(self.request)
        filtros = {
            "devo_empr": self.request.query_params.get("devo_empr"),
            "devo_fili": self.request.query_params.get("devo_fili"),
            "devo_pedi": self.request.query_params.get("devo_pedi"),
            "devo_data": self.request.query_params.get("devo_data"),
        }
        return DevolucaoPedidoPisoService.listar(banco, filtros=filtros)

    def create(self, request, *args, **kwargs):
        banco = get_licenca_db_config(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pedido_numero = serializer.validated_data.get("devo_pedi")
        usuario = serializer.validated_data.get("devo_usua")
        desconto = serializer.validated_data.get("devo_desc")
        data_devolucao = serializer.validated_data.get("devo_data")
        itens = serializer.validated_data.pop("itens", None)
        tipo = serializer.validated_data.pop("tipo", "DEVO")

        devolucao = DevolucaoPedidoPisoService.criar_ou_atualizar_por_pedido(
            banco=banco,
            pedido_numero=pedido_numero,
            usuario=usuario,
            tipo=tipo,
            desconto=desconto,
            data_devolucao=data_devolucao,
            itens=itens,
        )
        out = self.get_serializer(devolucao)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        banco = get_licenca_db_config(request)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)

        devolucao = DevolucaoPedidoPisoService.criar_ou_atualizar_por_pedido(
            banco=banco,
            pedido_numero=instance.devo_pedi,
            usuario=serializer.validated_data.get("devo_usua"),
            tipo=serializer.validated_data.pop("tipo", "DEVO"),
            desconto=serializer.validated_data.get("devo_desc", instance.devo_desc),
            data_devolucao=serializer.validated_data.get("devo_data", instance.devo_data),
            itens=serializer.validated_data.pop("itens", None),
        )
        return Response(self.get_serializer(devolucao).data)
