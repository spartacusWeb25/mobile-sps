# Localidades/rest/viewsets.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.utils import get_licenca_db_config
from localidades.models import Estados, Paises, Cidades
from localidades.services.ibge_service import IBGEService, IBGEServiceError
from .serializers import EstadosSerializer, PaisesSerializer, CidadesSerializer


class MultiBancoViewSet(viewsets.ModelViewSet):
    """
    ViewSet base que resolve o banco da licença (multibanco)
    e o injeta no contexto dos serializers.
    """

    model = None

    @property
    def banco(self):
        return get_licenca_db_config(self.request) or "default"

    def get_queryset(self):
        return self.model.objects.using(self.banco).all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["banco"] = self.banco
        return context

    def perform_destroy(self, instance):
        instance.delete(using=self.banco)


class EstadosViewSet(MultiBancoViewSet):
    model = Estados
    serializer_class = EstadosSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        nome = (self.request.query_params.get("nome") or "").strip()
        sigla = (self.request.query_params.get("sigla") or "").strip().upper()

        if nome:
            qs = qs.filter(esta_nome__icontains=nome)
        if sigla:
            qs = qs.filter(esta_sigl=sigla)

        return qs.order_by("esta_nome")

    @action(detail=False, methods=["post"], url_path="sincronizar-ibge")
    def sincronizar_ibge(self, request, *args, **kwargs):
        try:
            resultado = IBGEService.sincronizar_estados(self.banco)
            return Response(resultado, status=status.HTTP_200_OK)
        except IBGEServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class PaisesViewSet(MultiBancoViewSet):
    model = Paises
    serializer_class = PaisesSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        nome = (self.request.query_params.get("nome") or "").strip()
        if nome:
            qs = qs.filter(pais_nome__icontains=nome)

        return qs.order_by("pais_nome")

    @action(detail=False, methods=["post"], url_path="sincronizar-ibge")
    def sincronizar_ibge(self, request, *args, **kwargs):
        try:
            resultado = IBGEService.sincronizar_paises(self.banco)
            return Response(resultado, status=status.HTTP_200_OK)
        except IBGEServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class CidadesViewSet(MultiBancoViewSet):
    model = Cidades
    serializer_class = CidadesSerializer

    def get_queryset(self):
        qs = super().get_queryset().select_related("cida_esta", "cida_pais")

        nome = (self.request.query_params.get("nome") or "").strip()
        uf = (self.request.query_params.get("uf") or "").strip().upper()

        if nome:
            qs = qs.filter(cida_nome__icontains=nome)
        if uf:
            qs = qs.filter(cida_sigl=uf)

        return qs.order_by("cida_nome")

    @action(detail=False, methods=["post"], url_path="importar-ibge")
    def importar_ibge(self, request, *args, **kwargs):
        """
        Importa uma cidade pelo código IBGE.
        Body: {"codigo_ibge": 4119905}
        """
        codigo_ibge = request.data.get("codigo_ibge")
        if not codigo_ibge:
            return Response(
                {"detail": "Informe 'codigo_ibge'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cidade, criada = IBGEService.obter_ou_criar_cidade(
                banco=self.banco, codigo_ibge=codigo_ibge
            )
        except IBGEServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        serializer = self.get_serializer(cidade)
        return Response(
            {"criada": criada, "cidade": serializer.data},
            status=status.HTTP_201_CREATED if criada else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="sincronizar-ibge")
    def sincronizar_ibge(self, request, *args, **kwargs):
        try:
            resultado = IBGEService.sincronizar_cidades(self.banco)
            return Response(resultado, status=status.HTTP_200_OK)
        except IBGEServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=False, methods=["post"], url_path="sincronizar-tudo-ibge")
    def sincronizar_tudo_ibge(self, request, *args, **kwargs):
        try:
            resultado = IBGEService.sincronizar_tudo(self.banco)
            return Response(resultado, status=status.HTTP_200_OK)
        except IBGEServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
