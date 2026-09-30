from sympy import false

from ..models import OcorrenciaTransp, PerfilOcorrencia
from ..services.ocorrencia_service import OcorrenciaService
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from .serializers import OcorrenciaSerializer, PerfilSerializer

from core.utils import get_db_from_slug

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


class OcorrenciaTranspViewSet(BaseMultiDBViewSet):
    serializer_class = OcorrenciaSerializer

    def get_queryset(self):
        cfg = self._ctx()
        qs = OcorrenciaTransp.objects.using(cfg["db_alias"]).filter(
            ocor_empr=cfg["empresa"], ocor_fili=cfg["filial"]
        )
        codigo_param = (self.request.GET.get('codigo') or '').strip()
        descricao_param = (self.request.GET.get('descricao') or '').strip()

        if codigo_param:
            qs = qs.filter(ocor_codi__icontains=codigo_param)

        if descricao_param:
            qs = qs.filter(ocor_desc__icontains=descricao_param)

        return qs

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ocorrencia = OcorrenciaService.criar_ocorrencia(
            banco=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            codigo=data.get("ocor_codi", ""),
            descricao=data.get("ocor_desc", ""),
            finalizadora=data.get("ocor_fina", False),
        )
        return Response(self.get_serializer(ocorrencia).data, status=status.HTTP_201_CREATED)

class PerfilOcorrenciaViewSet(BaseMultiDBViewSet):
    serializer_class = PerfilSerializer

    def get_queryset(self):
        cfg = self._ctx()
        qs = PerfilOcorrencia.objects.using(cfg["db_alias"]).filter(
            pfoc_empr=cfg["empresa"], pfoc_fili=cfg["filial"]
        ).prefetch_related("ocorrencias")

        descricao_param = (self.request.GET.get('descricao') or '').strip()
        inativo_param = self.request.GET.get("inativo", "false").lower() == "true"

        if descricao_param:
            qs = qs.filter(pfoc_desc__icontains=descricao_param)

        if not inativo_param:
            qs = qs.filter(pfoc_ativ=True)

        return qs

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        perfil = OcorrenciaService.criar_perfil(
            banco=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            descricao=data.get("pfoc_desc"),
            ativo=data.get("pfoc_ativ", True),
            ocorrencias=data.get("ocorrencias", []),
        )
        return Response(self.get_serializer(perfil).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        perfil_id = kwargs.get("pk")

        perfil = OcorrenciaService.atualizar_perfil(
            banco=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            id=perfil_id,
            descricao=data["pfoc_desc"],
            ocorrencias=data.get("ocorrencias", []),
        )
        return Response(self.get_serializer(perfil).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def toggle_ativo(self, request, *args, **kwargs):
        cfg = self._ctx()
        perfil_id = kwargs.get("pk")

        perfil = OcorrenciaService.perfil_toggle_ativar(
            banco = cfg["db_alias"],
            empresa = cfg["empresa"],
            filial = cfg["filial"],
            id = perfil_id,
        )
        return Response(self.get_serializer(perfil).data, status=status.HTTP_200_OK)