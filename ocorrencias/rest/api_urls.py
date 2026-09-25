from rest_framework.routers import DefaultRouter

from ocorrencias.rest.viewsets import (
    OcorrenciaTranspViewSet,
    PerfilOcorrenciaViewSet,
)

router = DefaultRouter()
router.register(r"ocorrencias/", OcorrenciaTranspViewSet, basename="ocorrencia")
router.register(r"ocorrencias/perfis/", PerfilOcorrenciaViewSet, basename="perfil-ocorrencia")

urlpatterns = router.urls
