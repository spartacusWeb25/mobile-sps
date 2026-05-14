import json

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from core.utils import get_licenca_db_config

from ..Web.forms_trib import TributoForm
from ..models import CFOP
from ..services.tributos_service import TributoService
from .serializers import (
    CFOPSerializer,
    TributoSpartacusCloneSerializer,
    TributoSpartacusSerializer,
)


class CFOPViewSet(viewsets.ModelViewSet):
    serializer_class = CFOPSerializer
    lookup_value_regex = r"\d+"

    def get_banco(self):
        return get_licenca_db_config(self.request) or "default"

    def get_empresa_id(self):
        return (
            self.request.query_params.get("empresa_id")
            or self.request.headers.get("X-Empresa")
            or self.request.session.get("empresa_id")
            or self.request.headers.get("Empresa_id")
        )

    def get_queryset(self):
        banco = self.get_banco()
        empresa_id = self.get_empresa_id()
        q = self.request.query_params.get("q", "").strip() or self.request.query_params.get("term", "").strip()

        qs = CFOP.objects.using(banco).all()

        if empresa_id:
            try:
                qs = qs.filter(cfop_empr=int(empresa_id))
            except Exception:
                pass

        if q:
            qs = qs.filter(Q(cfop_codi__icontains=q) | Q(cfop_desc__icontains=q))

        return qs.order_by("cfop_codi")

    def list(self, request, *args, **kwargs):
        if str(request.query_params.get("select") or "").strip() in ("1", "true", "True"):
            banco = self.get_banco()
            empresa_id = self.get_empresa_id()
            q = request.query_params.get("q", "").strip() or request.query_params.get("term", "").strip()

            qs = CFOP.objects.using(banco).all()
            if empresa_id:
                try:
                    qs = qs.filter(cfop_empr=int(empresa_id))
                except Exception:
                    pass

            if q:
                qs = qs.filter(Q(cfop_codi__icontains=q) | Q(cfop_desc__icontains=q))

            qs = qs.only("cfop_id", "cfop_codi", "cfop_desc").order_by("cfop_codi")[:20]

            return Response(
                [{"value": str(x.cfop_id), "label": f"{x.cfop_codi} • {x.cfop_desc}"} for x in qs]
            )

        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        banco = self.get_banco()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        empresa_id = self.get_empresa_id()
        if empresa_id:
            try:
                data["cfop_empr"] = int(empresa_id)
            except Exception:
                pass

        obj = CFOP.objects.using(banco).create(**data)
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        banco = self.get_banco()
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        empresa_id = self.get_empresa_id()
        if empresa_id:
            try:
                setattr(instance, "cfop_empr", int(empresa_id))
            except Exception:
                pass

        for attr, value in serializer.validated_data.items():
            setattr(instance, attr, value)

        instance.save(using=banco)
        return Response(self.get_serializer(instance).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        instance.delete(using=self.get_banco())


class TributoSpartacusViewSet(viewsets.ViewSet):
    def get_banco(self):
        return get_licenca_db_config(self.request) or "default"

    def get_empresa_id(self):
        return (
            self.request.query_params.get("empresa_id")
            or self.request.data.get("empresa")
            or self.request.headers.get("X-Empresa")
            or self.request.session.get("empresa_id")
            or self.request.headers.get("Empresa_id")
        )

    def get_filial_id(self):
        return (
            self.request.query_params.get("filial_id")
            or self.request.data.get("filial")
            or self.request.headers.get("X-Filial")
            or self.request.session.get("filial_id")
            or self.request.headers.get("Filial_id")
            or 1
        )

    def get_service(self):
        return TributoService(
            banco=self.get_banco(),
            empresa=self.get_empresa_id(),
            filial=self.get_filial_id(),
        )

    def _get_request_data(self):
        if isinstance(self.request.data, dict):
            return self.request.data
        try:
            return json.loads(self.request.body or "{}")
        except Exception:
            return {}

    def list(self, request, *args, **kwargs):
        codigo = str(request.query_params.get("codigo") or "").strip()
        tipo = str(request.query_params.get("tipo") or "P").strip().upper()[:1] or "P"
        if not codigo:
            return Response({"detail": "Informe o codigo do produto."}, status=status.HTTP_400_BAD_REQUEST)

        service = self.get_service()
        rows = list(service.listar(codigo=codigo, tipo=tipo))
        serializer = TributoSpartacusSerializer(rows, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        payload = self._get_request_data().copy()
        payload.setdefault("empresa", self.get_empresa_id())
        payload.setdefault("filial", self.get_filial_id())
        payload.setdefault("tipo", "P")

        form = TributoForm(payload)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

        service = self.get_service()
        obj = service.salvar(form.to_service_data())
        return Response(TributoSpartacusSerializer(obj).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        payload = self._get_request_data().copy()
        payload.setdefault("empresa", self.get_empresa_id())
        payload.setdefault("filial", self.get_filial_id())
        payload.setdefault("tipo", "P")

        form = TributoForm(payload)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

        service = self.get_service()
        obj = service.salvar(form.to_service_data())
        return Response(TributoSpartacusSerializer(obj).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        payload = self._get_request_data()
        codigo = str(payload.get("codigo") or request.query_params.get("codigo") or "").strip()
        estado = str(payload.get("estado") or request.query_params.get("estado") or "").strip()
        entidade = str(payload.get("entidade") or request.query_params.get("entidade") or "").strip()
        tipo = str(payload.get("tipo") or request.query_params.get("tipo") or "P").strip()

        if not (codigo and estado and entidade):
            return Response(
                {"detail": "Informe codigo, estado e entidade para excluir."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted = self.get_service().excluir(
            codigo=codigo,
            estado=estado,
            entidade=entidade,
            tipo=tipo,
        )
        return Response({"deleted": deleted})

    @action(detail=False, methods=["post"], url_path="clone")
    def clone(self, request, *args, **kwargs):
        serializer = TributoSpartacusCloneSerializer(data=self._get_request_data())
        serializer.is_valid(raise_exception=True)

        service = self.get_service()
        rows = service.clonar(**serializer.validated_data)
        return Response(TributoSpartacusSerializer(rows, many=True).data, status=status.HTTP_201_CREATED)
