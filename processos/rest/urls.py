from rest_framework.routers import DefaultRouter

from processos.rest.viewsets import (
    ChecklistItemViewSet,
    ChecklistModeloViewSet,
    ProcessoViewSet,
)

router = DefaultRouter()
router.register(r"checklist-modelos", ChecklistModeloViewSet, basename="checklist-modelos")
router.register(r"checklist-itens", ChecklistItemViewSet, basename="checklist-itens")
router.register(r"processos", ProcessoViewSet, basename="processos")

urlpatterns = router.urls
