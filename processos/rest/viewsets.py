from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from core.utils import get_db_from_slug
from processos.models import ChecklistItem, ChecklistModelo, Processo, ProcessoTipo
from processos.rest.serializers import (
    ChecklistItemSerializer,
    ChecklistModeloSerializer,
    ProcessoChecklistRespostaSerializer,
    ProcessoSerializer,
    ProcessoTipoSerializer,
)
from processos.services.checklist_service import ChecklistService
from processos.services.processo_service import ProcessoService
from processos.services.validacao_service import ValidacaoProcessoService


class BaseMultiDBViewSet(viewsets.ModelViewSet):
    """Base REST do app Processos com roteamento por slug + escopo empresa/filial."""

    def _scope_value(self, session_key, header_key, query_key):
        return (
            self.request.session.get(session_key)
            or self.request.headers.get(header_key)
            or self.request.query_params.get(query_key)
        )

    def _ctx(self):
        slug = self.kwargs.get("slug")
        empresa = self._scope_value("empresa_id", "X-Empresa", "empresa")
        filial = self._scope_value("filial_id", "X-Filial", "filial")

        if not empresa or not filial:
            raise ValidationError(
                {
                    "detail": "Informe empresa e filial pela sessão, headers X-Empresa/X-Filial ou query params empresa/filial."
                }
            )

        try:
            empresa = int(empresa)
            filial = int(filial)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"detail": "Empresa e filial devem ser inteiros."}
            ) from exc

        return {
            "slug": slug,
            "db_alias": get_db_from_slug(slug) if slug else "default",
            "empresa": empresa,
            "filial": filial,
            "usuario_id": self.request.session.get("usuario_id")
            or self.request.headers.get("X-Usuario"),
        }

    def _not_found(
        self, message="Registro não encontrado para a empresa/filial informada."
    ):
        raise NotFound({"detail": message})


class ProcessoTipoViewSet(BaseMultiDBViewSet):
    serializer_class = ProcessoTipoSerializer

    def get_queryset(self):
        cfg = self._ctx()
        return ProcessoTipo.objects.using(cfg["db_alias"]).filter(
            prot_empr=cfg["empresa"], prot_fili=cfg["filial"]
        )

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tipo = ProcessoService.criar_tipo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            nome=data["prot_nome"],
            codigo=data["prot_codi"],
            ativo=data.get("prot_ativ", True),
        )
        return Response(self.get_serializer(tipo).data, status=status.HTTP_201_CREATED)


class ChecklistModeloViewSet(BaseMultiDBViewSet):
    serializer_class = ChecklistModeloSerializer

    def get_queryset(self):
        cfg = self._ctx()
        return (
            ChecklistModelo.objects.using(cfg["db_alias"])
            .filter(chmo_empr=cfg["empresa"], chmo_fili=cfg["filial"])
            .select_related("chmo_proc_tipo")
            .order_by("chmo_proc_tipo__prot_nome", "-chmo_vers", "chmo_nome")
        )

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            tipo = ProcessoTipo.objects.using(cfg["db_alias"]).get(
                id=data["chmo_proc_tipo_id"],
                prot_empr=cfg["empresa"],
                prot_fili=cfg["filial"],
                prot_ativ=True,
            )
        except ObjectDoesNotExist:
            self._not_found(
                "Tipo de processo não encontrado/ativo para a empresa e filial informadas."
            )

        modelo = ChecklistService.criar_modelo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo_tipo=tipo,
            nome=data["chmo_nome"],
            versao=data.get("chmo_vers", 1),
            ativo=data.get("chmo_ativ", True),
        )
        return Response(
            self.get_serializer(modelo).data, status=status.HTTP_201_CREATED
        )


class ChecklistItemViewSet(BaseMultiDBViewSet):
    serializer_class = ChecklistItemSerializer

    def get_queryset(self):
        cfg = self._ctx()
        return (
            ChecklistItem.objects.using(cfg["db_alias"])
            .filter(chit_empr=cfg["empresa"], chit_fili=cfg["filial"])
            .select_related("chit_mode", "chit_mode__chmo_proc_tipo")
            .order_by("chit_mode_id", "chit_orde")
        )

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            modelo = ChecklistModelo.objects.using(cfg["db_alias"]).get(
                id=data["chit_mode_id"],
                chmo_empr=cfg["empresa"],
                chmo_fili=cfg["filial"],
                chmo_ativ=True,
            )
        except ObjectDoesNotExist:
            self._not_found(
                "Modelo de checklist não encontrado/ativo para a empresa e filial informadas."
            )

        item = ChecklistService.criar_item(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            modelo=modelo,
            descricao=data["chit_desc"],
            ordem=data.get("chit_orde", 0),
            obrigatorio=data.get("chit_obri", True),
        )
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)


class ProcessoViewSet(BaseMultiDBViewSet):
    serializer_class = ProcessoSerializer

    def get_queryset(self):
        cfg = self._ctx()
        return ProcessoService.listar(
            db_alias=cfg["db_alias"], empresa=cfg["empresa"], filial=cfg["filial"]
        ).prefetch_related("respostas__pchr_item")

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        processo = ProcessoService.criar(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            tipo_id=data["proc_tipo_id"],
            descricao=data["proc_desc"],
            usuario_id=cfg["usuario_id"],
        )
        return Response(
            self.get_serializer(processo).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"], url_path="checklist")
    def checklist(self, request, pk=None, slug=None):
        cfg = self._ctx()
        processo = self.get_object()
        ChecklistService.gerar_respostas_para_processo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo=processo,
        )
        respostas = (
            processo.respostas.using(cfg["db_alias"])
            .filter(pchr_empr=cfg["empresa"], pchr_fili=cfg["filial"])
            .select_related("pchr_item")
            .order_by("pchr_item__chit_orde")
        )
        return Response(ProcessoChecklistRespostaSerializer(respostas, many=True).data)

    @action(detail=True, methods=["post"], url_path="salvar-checklist")
    def salvar_checklist(self, request, pk=None, slug=None):
        cfg = self._ctx()
        dados = request.data.get("respostas", {})
        respostas = ChecklistService.salvar_respostas(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo_id=pk,
            dados=dados,
        )
        return Response(
            {
                "ok": True,
                "respostas": ProcessoChecklistRespostaSerializer(
                    respostas, many=True
                ).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="validar")
    def validar(self, request, pk=None, slug=None):
        cfg = self._ctx()
        resultado = ValidacaoProcessoService.validar_processo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo_id=pk,
            usuario_id=cfg["usuario_id"],
        )
        return Response(resultado)
