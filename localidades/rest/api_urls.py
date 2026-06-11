# Localidades/rest/api_urls.py

from rest_framework.routers import DefaultRouter

from .viewsets import EstadosViewSet, PaisesViewSet, CidadesViewSet

router = DefaultRouter()
router.register(r"estados", EstadosViewSet, basename="estados")
router.register(r"paises", PaisesViewSet, basename="paises")
router.register(r"cidades", CidadesViewSet, basename="cidades")

urlpatterns = router.urls
