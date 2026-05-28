from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models.expressions import RawSQL
from .base import BaseMultiDBModelViewSet
from ..models import Ordemservico, Ordemservicopecas, Ordemservicoservicos, OrdemServicoFaseSetor, OrdemServicoVoltagem, Osarquivos
from ..serializers import OrdemServicoSerializer, OsArquSerializer
from ..filters.os import OrdemServicoFilter
from ..pagination import OrdemServicoPagination
from ..permissions import OrdemServicoPermission, PodeVerOrdemDoSetor, WorkflowPermission
from Entidades.models import Entidades

from ..services import workflow_service, ordem_service, total_service
from ..services.os_arquivo_service import OsArquivoService
from ..handlers.dominio_handler import tratar_erro
from django.db.models import Q, Case, When, Value, DateField
from Agricola.service.sequencial_Service import SequencialService
import base64

import logging
logger = logging.getLogger(__name__)

class SafeOrderingFilter(filters.OrderingFilter):
    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if ordering:
            return [o.replace('orde_data_aber', 'safe_data_aber') for o in ordering]
        return ordering

class OrdemViewSet(BaseMultiDBModelViewSet):
    queryset = Ordemservico.objects.none() 
    modulo_necessario = 'OrdemdeServico'
    serializer_class = OrdemServicoSerializer
    filter_backends = [DjangoFilterBackend, SafeOrderingFilter, filters.SearchFilter]
    filterset_class = OrdemServicoFilter
    ordering_fields = ['orde_data_aber', 'safe_data_aber', 'orde_data_fech', 'orde_prio']
    search_fields = ['orde_prob', 'orde_defe_desc', 'orde_obse', 'orde_nume']
    permission_classes = [IsAuthenticated, OrdemServicoPermission, PodeVerOrdemDoSetor]
    pagination_class = OrdemServicoPagination
    lookup_field = "orde_nume"

    def _get_empresa_filial(self, request):
        empresa = (
            request.headers.get("X-Empresa")
            or request.query_params.get("empresa")
            or request.query_params.get("empr")
            or request.data.get("empresa")
        )
        filial = (
            request.headers.get("X-Filial")
            or request.query_params.get("filial")
            or request.query_params.get("fili")
            or request.data.get("filial")
        )
        return empresa, filial

    def get_queryset(self):
        banco = self.get_banco()
        user_setor = getattr(self.request.user, 'setor', None)

        qs = Ordemservico.objects.using(banco).filter(
            orde_seto__isnull=False,
            orde_stat_orde__in=[0, 1, 2, 3, 5, 21, 22]
        ).exclude(orde_seto=0)

        # Usa only() para carregar apenas campos não-date
        # Isso evita que psycopg2 tente deserializar datas inválidas
        qs = qs.only(
            'orde_nume', 'orde_empr', 'orde_fili', 'orde_enti', 'orde_seto',
            'orde_stat_orde', 'orde_prio', 'orde_tipo', 'orde_prob', 'orde_defe_desc',
            'orde_obse', 'orde_plac', 'orde_tota', 'orde_gara', 'orde_sem_cons', 'orde_volt'
        )

        if user_setor and getattr(user_setor, "osfs_codi", None):
            qs = qs.filter(orde_seto=user_setor.osfs_codi)

        orde_nume = self.request.query_params.get('orde_nume')
        if orde_nume:
            qs = qs.filter(orde_nume=orde_nume)

        cliente_nome = self.request.query_params.get('cliente_nome')
        if cliente_nome:
            qs = qs.filter(
                orde_enti__in=Entidades.objects.using(banco)
                .filter(enti_nome__icontains=cliente_nome)
                .values_list('enti_clie', flat=True)[:500]
            )

        return qs.order_by('-orde_nume')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())

            page = self.paginate_queryset(queryset)
            if page is not None:
                # Na lista, não carrega peças/serviços completos, apenas contagens
                self._prefetch_counts(page)
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            self._prefetch_counts(queryset)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except ValueError as e:
            # Captura erro de data inválida e tenta filtrar o registro problemático
            if "year" in str(e).lower() and "out of range" in str(e).lower():
                logger.error(f"Erro de data inválida detectado: {e}")
                # Tenta buscar IDs válidos excluindo o registro problemático
                return self._list_with_error_handling(request)
            raise
        except Exception as e:
            logger.error(f"Erro ao listar ordens: {e}", exc_info=True)
            return tratar_erro(e)

    def retrieve(self, request, *args, **kwargs):
        """No detalhe, carrega todas as peças e serviços completos"""
        try:
            instance = self.get_object()
            # No detalhe, carrega peças e serviços completos
            self._prefetch_related_objects([instance])
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Exception as e:
            return tratar_erro(e)

    @action(detail=False, methods=['get'], url_path='contadores')
    def contadores(self, request):
        """Retorna contadores totais por status de todas as ordens"""
        try:
            banco = self.get_banco()
            
            # Contagem por status usando agregação do Django
            from django.db.models import Count
            
            contadores = Ordemservico.objects.using(banco).filter(
                orde_seto__isnull=False,
                orde_stat_orde__in=[0, 1, 2, 3, 5, 21, 22]
            ).exclude(orde_seto=0).values('orde_stat_orde').annotate(
                count=Count('orde_nume')
            )
            
            # Converte para dicionário
            contadores_dict = {item['orde_stat_orde']: item['count'] for item in contadores}
            
            # Calcula totais
            total = sum(contadores_dict.values())
            
            return Response({
                'abertas': contadores_dict.get(0, 0),
                'orcamento_gerado': contadores_dict.get(1, 0),
                'aguardando_liberacao': contadores_dict.get(2, 0),
                'liberadas': contadores_dict.get(3, 0),
                'reprovadas': contadores_dict.get(5, 0),
                'faturada_parcial': contadores_dict.get(20, 0),
                'atrasadas': contadores_dict.get(21, 0),
                'em_estoque': contadores_dict.get(22, 0),
                'total': total,
            })
        except Exception as e:
            logger.error(f"Erro ao buscar contadores: {e}", exc_info=True)
            return tratar_erro(e)

    def _list_with_error_handling(self, request):
        """Tenta listar ordens pulando registros com datas inválidas"""
        banco = self.get_banco()
        try:
            # Busca todos os IDs primeiro
            all_ids = list(Ordemservico.objects.using(banco)
                .filter(
                    orde_seto__isnull=False,
                    orde_stat_orde__in=[0, 1, 2, 3, 5, 21, 22]
                )
                .exclude(orde_seto=0)
                .values_list('orde_nume', flat=True)
            )
            
            # Tenta carregar em lotes, pulando registros com erro
            valid_objects = []
            batch_size = 100
            for i in range(0, len(all_ids), batch_size):
                batch_ids = all_ids[i:i + batch_size]
                try:
                    batch = list(Ordemservico.objects.using(banco)
                        .filter(orde_nume__in=batch_ids)
                        .only(
                            'orde_nume', 'orde_empr', 'orde_fili', 'orde_enti', 'orde_seto',
                            'orde_stat_orde', 'orde_prio', 'orde_tipo', 'orde_prob', 'orde_defe_desc',
                            'orde_obse', 'orde_plac', 'orde_tota', 'orde_gara', 'orde_sem_cons', 'orde_volt'
                        )
                    )
                    valid_objects.extend(batch)
                except ValueError as e:
                    logger.warning(f"Pulando lote com erro de data: {e}")
                    continue
            
            page = self.paginate_queryset(valid_objects)
            if page is not None:
                self._prefetch_counts(page)
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            self._prefetch_counts(valid_objects)
            serializer = self.get_serializer(valid_objects, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Erro no fallback de listagem: {e}", exc_info=True)
            return tratar_erro(e)

    def _prefetch_counts(self, objects):
        """Na lista, carrega apenas contagens de peças e serviços, não os objetos completos"""
        if not objects:
            return

        banco = self.get_banco()
        orde_ids = [obj.orde_nume for obj in objects]

        # Contagem de peças por ordem
        from django.db.models import Count
        pecas_counts = dict(Ordemservicopecas.objects.using(banco)
            .filter(peca_orde__in=orde_ids)
            .values('peca_orde')
            .annotate(count=Count('peca_id'))
            .values_list('peca_orde', 'count')
        )

        # Contagem de serviços por ordem
        servicos_counts = dict(Ordemservicoservicos.objects.using(banco)
            .filter(serv_orde__in=orde_ids)
            .values('serv_orde')
            .annotate(count=Count('serv_id'))
            .values_list('serv_orde', 'count')
        )

        # Prefetch Setores, Clientes e Voltagens (necessários para a lista)
        setor_ids = {obj.orde_seto for obj in objects if obj.orde_seto}
        if setor_ids:
            setores = OrdemServicoFaseSetor.objects.using(banco).filter(osfs_codi__in=setor_ids).only('osfs_codi', 'osfs_nome')
            setores_map = {s.osfs_codi: s.osfs_nome for s in setores}
        else:
            setores_map = {}

        clie_ids = {obj.orde_enti for obj in objects if obj.orde_enti}
        empr_ids = {obj.orde_empr for obj in objects if obj.orde_empr}
        if clie_ids and empr_ids:
            clientes = Entidades.objects.using(banco).filter(
                enti_clie__in=clie_ids,
                enti_empr__in=empr_ids
            ).only('enti_empr', 'enti_clie', 'enti_nome')
            clientes_map = {(c.enti_empr, c.enti_clie): c.enti_nome for c in clientes}
        else:
            clientes_map = {}

        volt_ids = {obj.orde_volt for obj in objects if obj.orde_volt}
        if volt_ids:
            voltagens = OrdemServicoVoltagem.objects.using(banco).filter(osvo_codi__in=volt_ids).only('osvo_codi', 'osvo_nome')
            voltagens_map = {v.osvo_codi: v.osvo_nome for v in voltagens}
        else:
            voltagens_map = {}

        # Assign to objects
        for obj in objects:
            obj._pecas_count = pecas_counts.get(obj.orde_nume, 0)
            obj._servicos_count = servicos_counts.get(obj.orde_nume, 0)
            obj._prefetched_setor_nome = setores_map.get(obj.orde_seto)
            obj._prefetched_cliente_nome = clientes_map.get((obj.orde_empr, obj.orde_enti))
            obj._prefetched_voltagem_nome = voltagens_map.get(obj.orde_volt)

    def _prefetch_related_objects(self, objects):
        if not objects:
            return

        banco = self.get_banco()
        orde_ids = [obj.orde_nume for obj in objects]

        # Prefetch Pecas - usando only() para carregar apenas campos necessários
        pecas = list(Ordemservicopecas.objects.using(banco)
            .filter(peca_orde__in=orde_ids)
            .only('peca_orde', 'peca_id', 'peca_codi', 'peca_comp', 'peca_quan', 'peca_unit', 'peca_tota', 'peca_tecn', 'peca_sem_esto'))
        pecas_map = {}
        for peca in pecas:
            pecas_map.setdefault(peca.peca_orde, []).append(peca)

        # Prefetch Servicos - usando only() para carregar apenas campos necessários
        servicos = list(Ordemservicoservicos.objects.using(banco)
            .filter(serv_orde__in=orde_ids)
            .only('serv_orde', 'serv_id', 'serv_sequ', 'serv_codi', 'serv_comp', 'serv_quan', 'serv_unit', 'serv_tota'))
        servicos_map = {}
        for serv in servicos:
            servicos_map.setdefault(serv.serv_orde, []).append(serv)

        # Prefetch Setores
        setor_ids = {obj.orde_seto for obj in objects if obj.orde_seto}
        if setor_ids:
            setores = OrdemServicoFaseSetor.objects.using(banco).filter(osfs_codi__in=setor_ids).only('osfs_codi', 'osfs_nome')
            setores_map = {s.osfs_codi: s.osfs_nome for s in setores}
        else:
            setores_map = {}

        # Prefetch Clientes - otimizado com only() e filter por empresa também
        clie_ids = {obj.orde_enti for obj in objects if obj.orde_enti}
        empr_ids = {obj.orde_empr for obj in objects if obj.orde_empr}
        if clie_ids and empr_ids:
            clientes = Entidades.objects.using(banco).filter(
                enti_clie__in=clie_ids,
                enti_empr__in=empr_ids
            ).only('enti_empr', 'enti_clie', 'enti_nome')
            clientes_map = {(c.enti_empr, c.enti_clie): c.enti_nome for c in clientes}
        else:
            clientes_map = {}

        # Prefetch Voltagens
        volt_ids = {obj.orde_volt for obj in objects if obj.orde_volt}
        if volt_ids:
            voltagens = OrdemServicoVoltagem.objects.using(banco).filter(osvo_codi__in=volt_ids).only('osvo_codi', 'osvo_nome')
            voltagens_map = {v.osvo_codi: v.osvo_nome for v in voltagens}
        else:
            voltagens_map = {}

        # Assign to objects
        for obj in objects:
            obj._prefetched_pecas = pecas_map.get(obj.orde_nume, [])
            obj._prefetched_servicos = servicos_map.get(obj.orde_nume, [])
            obj._prefetched_setor_nome = setores_map.get(obj.orde_seto)
            obj._prefetched_cliente_nome = clientes_map.get((obj.orde_empr, obj.orde_enti))
            obj._prefetched_voltagem_nome = voltagens_map.get(obj.orde_volt)

    def get_next_ordem_numero(self, empre, fili, data):
        """
        Temporário: recebe o número de ordem do frontend.
        Quando automatizado, voltará a calcular com base no último número do banco.
        """
        nova_ordem = data.get('orde_nume')
        if not nova_ordem:
            raise ValueError("Número da ordem é obrigatório enquanto o modo manual estiver ativo.")
        return nova_ordem

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        kwargs['view'] = self
        return kwargs

    def create(self, request, *args, **kwargs):
        try:
            banco = self.get_banco()
            # Copia dados para não mutar o request original se for imutável
            data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

            # Mapeamento de campos legado
            campo_mapping = {
                'os_clie': 'orde_enti',
                'os_data_aber': 'orde_data_aber',
                'os_empr': 'orde_empr',
                'os_fili': 'orde_fili',
                'usua': 'orde_usua_aber',
                'nf_entrada': 'orde_nf_entr',
                'os_nf_entr': 'orde_nf_entr',
                'os_gara': 'orde_gara',
                'os_sem_cons': 'orde_sem_cons',
                'os_data_repr': 'orde_data_repr',
                'os_seto_repr': 'orde_seto_repr',
                'os_fina_ofic': 'orde_fina_ofic',
                'os_stat_orde': 'orde_stat_orde',
                'os_orde_ante': 'orde_orde_ante',
                'os_nf_data': 'orde_nf_data',
            }
            
            for frontend_field, backend_field in campo_mapping.items():
                if frontend_field in data:
                    data[backend_field] = data.pop(frontend_field)

            data['orde_stat_orde'] = 0 if data.get('orde_stat_orde') is None else data.get('orde_stat_orde')
            if request.user and request.user.pk:
                data['orde_usua_aber'] = request.user.pk

            empre = data.get('orde_empr')
            fili = data.get('orde_fili')
            
            if not empre or not fili:
                # Tenta pegar dos campos mapeados ou originais se falhar
                empre = data.get('orde_empr')
                fili = data.get('orde_fili')
                if not empre or not fili:
                     return Response({"detail": "Empresa e Filial são obrigatórios."}, status=400)

            # Garantir número da OS
            try:
                data['orde_nume'] = self.get_next_ordem_numero(empre, fili, data)
            except ValueError as ve:
                 return Response({"detail": str(ve)}, status=400)
            
            # Injetar chaves estrangeiras nos itens para passar na validação do serializer
            # O Serializer valida a presença de peca_empr, peca_fili, peca_orde, etc.
            if 'pecas' in data and isinstance(data['pecas'], list):
                for peca in data['pecas']:
                    if isinstance(peca, dict):
                        peca['peca_empr'] = empre
                        peca['peca_fili'] = fili
                        peca['peca_orde'] = data['orde_nume']
            
            if 'servicos' in data and isinstance(data['servicos'], list):
                for servico in data['servicos']:
                    if isinstance(servico, dict):
                        servico['serv_empr'] = empre
                        servico['serv_fili'] = fili
                        servico['serv_orde'] = data['orde_nume']

            # Validação via Serializer para garantir integridade dos dados
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            
            # Extrai peças e serviços validados
            pecas_data = validated_data.pop('pecas', [])
            servicos_data = validated_data.pop('servicos', [])
            
            # Como o serializer retorna OrderedDicts, podemos passar adiante.
            # O service e repo esperam dicionários, OrderedDict é compatível.
            
            ordem = ordem_service.criar_ordem_servico(
                dados=validated_data,
                pecas_data=pecas_data,
                servicos_data=servicos_data,
                usuario=request.user,
                banco=banco
            )
            
            serializer = self.get_serializer(ordem)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            return tratar_erro(e)

    def update(self, request, *args, **kwargs):
        try:
            banco = self.get_banco()
            instance = self.get_object()
            data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
            
            # Para update, também validamos
            # Adicionamos skip_duplicate_check ao contexto para permitir que a validação de duplicidade
            # seja ignorada neste nível, delegando a resolução para o sync_pecas/sync_servicos
            context = self.get_serializer_context()
            context['skip_duplicate_check'] = True
            
            serializer = self.get_serializer(instance, data=data, partial=True, context=context)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            pecas_data = validated_data.pop('pecas', None)
            servicos_data = validated_data.pop('servicos', None)
            
            ordem = ordem_service.atualizar_ordem_servico(
                ordem=instance,
                dados=validated_data,
                pecas_data=pecas_data,
                servicos_data=servicos_data,
                usuario=request.user,
                banco=banco
            )
            
            serializer = self.get_serializer(ordem)
            return Response(serializer.data)
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=["post"], url_path="avancar-setor", permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor, WorkflowPermission])
    def avancar_setor(self, request, *args, **kwargs):
        banco = self.get_banco()
        ordem = self.get_object()
        setor_destino = request.data.get("setor_destino")

        if not setor_destino:
            return Response(
                {"erro": "campo_obrigatorio", "campo": "setor_destino"},
                status=400
            )

        try:
            with transaction.atomic(using=banco):
                ordem = workflow_service.avancar_setor(
                    ordem_model=ordem,
                    setor_destino=setor_destino,
                    usuario=request.user,
                    banco=banco
                )
            return Response(self.get_serializer(ordem).data)
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=["post"], url_path="retornar-setor", permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor, WorkflowPermission])
    def retornar_setor(self, request, *args, **kwargs):
        banco = self.get_banco()
        ordem = self.get_object()
        setor_origem = request.data.get("setor_origem") or request.data.get("setor_destino")

        if not setor_origem:
             return Response(
                {"erro": "campo_obrigatorio", "campo": "setor_origem"},
                status=400
            )

        try:
            with transaction.atomic(using=banco):
                ordem = workflow_service.retornar_setor(
                    ordem_model=ordem,
                    setor_origem=setor_origem,
                    usuario=request.user,
                    banco=banco
                )
            return Response(self.get_serializer(ordem).data)
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=["get"], url_path="proximos-setores", permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor, WorkflowPermission])
    def proximos_setores(self, request, *args, **kwargs):
        try:
            banco = self.get_banco()
            ordem = self.get_object()
            setores = workflow_service.listar_proximos_setores(ordem, banco)
            return Response({
                "proximos_setores": [
                    {
                        "codigo": setor.wkfl_seto_dest, 
                        "nome": f"Setor {setor.wkfl_seto_dest}",
                        "ordem": setor.wkfl_orde
                    }
                    for setor in setores
                ]
            })
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=["get"], url_path="anteriores-setores", permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor, WorkflowPermission])
    def anteriores_setores(self, request, *args, **kwargs):
        try:
            banco = self.get_banco()
            ordem = self.get_object()
            setores = workflow_service.listar_setores_anteriores(ordem, banco)
            return Response({
                "anteriores_setores": [
                    {
                        "codigo": setor.wkfl_seto_orig, 
                        "nome": f"Setor {setor.wkfl_seto_orig}"
                    }
                    for setor in setores
                ]
            })
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=['post'], url_path='atualizar-total', permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor, WorkflowPermission])
    def atualizar_total(self, request, *args, **kwargs):
        try:
            banco = self.get_banco()
            ordem = self.get_object()
            
            # Assumindo que itens_lista retorna um queryset ou lista iterável de peças
            total_service.atualizar_total(ordem, ordem.itens_lista, banco)
            
            serializer = self.get_serializer(ordem)
            return Response(serializer.data)
        except Exception as e:
            return tratar_erro(e)

    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor, WorkflowPermission],
        url_path="atualizar-prioridade"
    )
    def atualizar_prioridade(self, request, *args, **kwargs):
        """
        Atualiza apenas o campo de prioridade (orde_prio) da ordem.
        Exemplo JSON:
        {
            "orde_prio": 2
        }
        """
        try:
            banco = self.get_banco()
            ordem = self.get_object()

            nova_prioridade = request.data.get("orde_prio")
            if nova_prioridade is None:
                return Response(
                    {"erro": "O campo 'orde_prio' é obrigatório."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic(using=banco):
                ordem.orde_prio = int(nova_prioridade)
                ordem.save(using=banco, update_fields=["orde_prio"])
            serializer = self.get_serializer(ordem)
            return Response(
                {
                    "mensagem": "Prioridade atualizada com sucesso.",
                    "nova_prioridade": ordem.orde_prio,
                    "ordem": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return tratar_erro(e)

    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor, WorkflowPermission],
        url_path="motor-em-estoque"
    )
    def atualizar_motor_estoque(self, request, *args, **kwargs):
        """
        Atualiza o status da ordem de serviço para 22 (Motor em Estoque).
        """
        try:
            banco = self.get_banco()
            ordem = self.get_object()

            with transaction.atomic(using=banco):
                ordem.orde_stat_orde = 22
                ordem.save(using=banco, update_fields=["orde_stat_orde"])

            serializer = self.get_serializer(ordem)
            return Response(
                {
                    "mensagem": "Status do motor atualizado com sucesso.",
                    "motor_em_estoque": True,
                    "novo_status": ordem.orde_stat_orde,
                    "ordem": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=["get"], url_path="historico-workflow", permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor])
    def historico_workflow(self, request, *args, **kwargs):
        """
        Retorna o histórico de workflow da ordem.
        """
        try:
            banco = self.get_banco()
            ordem = self.get_object()
            
            # Importação local para evitar importação circular
            from ..models import Ordemservicoworkflowhistorico
            from ..serializers import HistoricoWorkflowSerializer
            
            queryset = Ordemservicoworkflowhistorico.objects.using(banco).filter(
                oswh_empr=ordem.orde_empr,
                oswh_fili=ordem.orde_fili,
                oswh_orde=ordem.orde_nume
            ).order_by('-oswh_data')
            
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = HistoricoWorkflowSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
                
            serializer = HistoricoWorkflowSerializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=["get"], url_path="arquivos", permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor])
    def arquivos(self, request, *args, **kwargs):
        try:
            banco = self.get_banco()
            os_nume = kwargs.get(self.lookup_field) or kwargs.get("pk")
            empresa, filial = self._get_empresa_filial(request)
            if not (empresa and filial):
                ordem = self.get_object()
                empresa, filial, os_nume = ordem.orde_empr, ordem.orde_fili, ordem.orde_nume

            queryset = Osarquivos.objects.using(banco).filter(
                arqu_empr=empresa,
                arqu_fili=filial,
                arqu_os=os_nume,
            ).order_by("-arqu_codi_arqu")

            page = self.paginate_queryset(queryset)
            objs = page if page is not None else queryset

            data = []
            for obj in objs:
                item = OsArquSerializer(obj, context={"banco": banco, "include_base64": True}).data
                prev = OsArquivoService.preview(obj)
                if isinstance(prev, bytes):
                    prev = base64.b64encode(prev).decode("utf-8")
                item["preview"] = prev
                data.append(item)

            if page is not None:
                return self.get_paginated_response(data)
            return Response(data)
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=["get"], url_path=r"arquivos/(?P<arquivo_id>\d+)", permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor])
    def arquivo(self, request, arquivo_id=None, *args, **kwargs):
        try:
            banco = self.get_banco()
            os_nume = kwargs.get(self.lookup_field) or kwargs.get("pk")
            empresa, filial = self._get_empresa_filial(request)
            if not (empresa and filial):
                ordem = self.get_object()
                empresa, filial, os_nume = ordem.orde_empr, ordem.orde_fili, ordem.orde_nume

            obj = Osarquivos.objects.using(banco).filter(
                arqu_empr=empresa,
                arqu_fili=filial,
                arqu_os=os_nume,
                arqu_codi_arqu=arquivo_id,
            ).first()

            if not obj:
                return Response({"detail": "Arquivo não encontrado."}, status=status.HTTP_404_NOT_FOUND)

            data = OsArquSerializer(obj, context={"banco": banco, "include_base64": True}).data
            prev = OsArquivoService.preview(obj)
            if isinstance(prev, bytes):
                prev = base64.b64encode(prev).decode("utf-8")
            data["preview"] = prev
            return Response(data)
        except Exception as e:
            return tratar_erro(e)

    @action(detail=True, methods=["post", "patch"], url_path="arquivos/upload", permission_classes=[IsAuthenticated, PodeVerOrdemDoSetor])
    def upload_arquivos(self, request, *args, **kwargs):
        try:
            banco = self.get_banco()
            os_nume = kwargs.get(self.lookup_field) or kwargs.get("pk")
            arquivos = request.data.get("arquivos")

            user = (
                getattr(request.user, "pk", None)
                or request.data.get("usua")
                or request.data.get("usuario")
                or request.data.get("usuario_id")
                or 0
            )
            empresa, filial = self._get_empresa_filial(request)
            if not (empresa and filial):
                ordem = self.get_object()
                empresa, filial, os_nume = ordem.orde_empr, ordem.orde_fili, ordem.orde_nume

            if isinstance(arquivos, str):
                obj = OsArquivoService.salvar_um(os_nume, arquivos, user, empresa, filial, banco=banco)
                data = OsArquSerializer(obj, context={"banco": banco}).data if obj else None
                return Response({"msg": "1 arquivo enviado", "arquivo": data})

            if isinstance(arquivos, list):
                objs = OsArquivoService.salvar_multiplos(os_nume, arquivos, user, empresa, filial, banco=banco)
                data = [OsArquSerializer(o, context={"banco": banco}).data for o in objs]
                return Response({"msg": f"{len(objs)} arquivos enviados", "arquivos": data})

            return Response({"erro": "formato inválido"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return tratar_erro(e)
