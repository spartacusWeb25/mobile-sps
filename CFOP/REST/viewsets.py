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

    @action(detail=False, methods=["get"], url_path="ibscbs-classificacoes")
    def ibscbs_classificacoes(self, request, *args, **kwargs):
        banco = self.get_banco()
        empresa_id = self.get_empresa_id()
        filial_id = self.get_filial_id()
        ncm_raw = str(request.query_params.get("ncm") or "").strip()
        ncm_digits = "".join(ch for ch in ncm_raw if ch.isdigit())

        try:
            from Produtos.models import Produtos
        except Exception:
            return Response(
                {"detail": "Produtos não disponível para consulta por NCM."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        from ..models_tributos import Tributos

        def normalize_cclasstrib(v: str) -> str | None:
            s = str(v or "").strip()
            if not s:
                return None
            digits = "".join(ch for ch in s if ch.isdigit())
            if not digits:
                return None
            return digits.zfill(6)[:6]

        from collections import Counter

        counter = Counter()
        fontes = []

        try:
            from Notas_Fiscais.models import NotaItem

            nota_qs = NotaItem.objects.using(banco).select_related("nota").filter(nota__status=100)

            ncm8 = ncm_digits[:8] if len(ncm_digits) >= 8 else ""
            ncm4 = ncm_digits[:4] if len(ncm_digits) >= 4 else ""

            if ncm8:
                nota_qs = nota_qs.filter(ncm=ncm8)
            elif ncm4:
                nota_qs = nota_qs.filter(ncm__startswith=ncm4)

            for v in nota_qs.values_list("ibscbs_cclasstrib", flat=True):
                code = normalize_cclasstrib(v)
                if code and code != "000000":
                    counter[code] += 10

            if counter:
                fontes.append("NOTAS")
        except Exception:
            pass

        trib_qs = Tributos.objects.using(banco).all()
        if empresa_id not in (None, ""):
            try:
                trib_qs = trib_qs.filter(trib_empr=int(empresa_id))
            except Exception:
                pass
        if filial_id not in (None, ""):
            try:
                trib_qs = trib_qs.filter(trib_fili=int(filial_id))
            except Exception:
                pass

        if ncm_digits:
            prefix8 = ncm_digits[:8]
            prefix4 = ncm_digits[:4] if len(ncm_digits) >= 4 else ""

            prod_qs = Produtos.objects.using(banco).all()
            if empresa_id not in (None, ""):
                try:
                    prod_qs = prod_qs.filter(prod_empr=str(int(empresa_id)))
                except Exception:
                    pass

            prod_codes = list(
                prod_qs.filter(prod_ncm__startswith=prefix8).values_list("prod_codi", flat=True)[:2000]
            )
            if not prod_codes and prefix4:
                prod_codes = list(
                    prod_qs.filter(prod_ncm__startswith=prefix4).values_list("prod_codi", flat=True)[:2000]
                )

            if prod_codes:
                trib_qs = trib_qs.filter(trib_codi__in=prod_codes)

        for r in trib_qs.values_list("trib_ibscbs_cclasstrib", "trib_ibscbs_cclasstribreg"):
            c1 = normalize_cclasstrib(r[0])
            c2 = normalize_cclasstrib(r[1])
            if c1 and c1 != "000000":
                counter[c1] += 1
            if c2 and c2 != "000000":
                counter[c2] += 1

        if not fontes:
            fontes.append("TRIBUTOS")

        opcoes = [
            {"value": code, "count": int(count)}
            for code, count in counter.most_common(200)
        ]
        return Response(
            {
                "ncm": ncm_raw or None,
                "ncm_digits": ncm_digits or None,
                "fontes": fontes,
                "opcoes": opcoes,
            }
        )
