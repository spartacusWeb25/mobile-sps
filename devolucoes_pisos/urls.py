from django.urls import include, path
from rest_framework.routers import DefaultRouter

from devolucoes_pisos.rest.views import DevolucaoPisosViewSet

router = DefaultRouter()
router.register(r"devolucoes", DevolucaoPisosViewSet, basename="devolucoes_pisos")

urlpatterns = [
    path("", include(router.urls)),
]

