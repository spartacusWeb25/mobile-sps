from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixin import DBAndSlugMixin
from nfse.models import Nfse
from nfse.Rest.serializers import (
    EmitirNfseSerializer,
    NfseDetailSerializer,
    NfseSerializer,
)
from nfse.services.cancelamento_service import CancelamentoNfseService
from nfse.services.consulta_service import ConsultaNfseService
from nfse.services.context import NfseContext
from nfse.services.emissao_service import EmissaoNfseService
from Produtos.models import Produtos


class NfseViewSet(DBAndSlugMixin, viewsets.ViewSet):
    def list(self, request, slug=None):
        context = NfseContext.from_request(request, slug)
        queryset = (
            Nfse.objects.using(context.db_alias)
            .filter(
                nfse_empr=context.empresa_id,
                nfse_fili=context.filial_id,
            )
            .order_by('-nfse_id')
        )
        serializer = NfseSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None, slug=None):
        context = NfseContext.from_request(request, slug)
        nfse = (
            Nfse.objects.using(context.db_alias)
            .filter(
                nfse_id=pk,
                nfse_empr=context.empresa_id,
                nfse_fili=context.filial_id,
            )
            .first()
        )

        if not nfse:
            return Response({'detail': 'NFS-e não encontrada'}, status=404)

        serializer = NfseDetailSerializer(nfse)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='emitir')
    def emitir(self, request, slug=None):
        serializer = EmitirNfseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        context = NfseContext.from_request(request, slug)
        nfse = EmissaoNfseService.emitir(context, serializer.validated_data)

        nfse_atualizada = (
            Nfse.objects.using(context.db_alias)
            .filter(nfse_id=nfse.pk)
            .first()
        )

        return Response(
            NfseDetailSerializer(nfse_atualizada).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'], url_path='consultar')
    def consultar(self, request, pk=None, slug=None):
        context = NfseContext.from_request(request, slug)
        retorno = ConsultaNfseService.consultar(context, int(pk))
        return Response(retorno)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None, slug=None):
        motivo = request.data.get('motivo')
        if not motivo:
            return Response({'motivo': 'Informe o motivo do cancelamento'}, status=400)

        context = NfseContext.from_request(request, slug)
        nfse = CancelamentoNfseService.cancelar(context, int(pk), motivo)

        nfse_atualizada = (
            Nfse.objects.using(context.db_alias)
            .filter(nfse_id=nfse.pk)
            .first()
        )

        return Response(NfseDetailSerializer(nfse_atualizada).data)

    @action(detail=False, methods=['get'], url_path='autocomplete-servicos')
    def autocomplete_servicos(self, request, slug=None):
        """Autocomplete para serviços cadastrados no sistema"""
        context = NfseContext.from_request(request, slug)
        query = request.GET.get('q', '').strip()
        
        if not query:
            return Response([])
        
        queryset = (
            Produtos.objects.using(context.db_alias)
            .filter(
                prod_e_serv=True,
                prod_empr=str(context.empresa_id)
            )
            .filter(
                prod_desc_serv__icontains=query
            )
        )
        
        if len(query) >= 3:
            queryset = queryset.filter(prod_codi__icontains=query)
        
        results = []
        for servico in queryset[:20]:
            results.append({
                'value': servico.prod_codi,
                'label': f"{servico.prod_codi} - {servico.prod_desc_serv}",
                'codigo_servico': servico.prod_codi_serv or '',
                'descricao_servico': servico.prod_desc_serv or '',
                'cnae': servico.prod_cnae or '',
                'iss_aliquota': float(servico.prod_iss) if servico.prod_iss else 0,
                'iss_exigivel': servico.prod_exig_iss or 1,
            })
        
        return Response(results)