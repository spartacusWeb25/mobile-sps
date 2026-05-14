from django.urls import path
from rest_framework.routers import DefaultRouter
from .viewsets import CFOPViewSet, TributoSpartacusViewSet

router = DefaultRouter()
router.register(r"cfop", CFOPViewSet, basename="cfop")
router.register(r"cfop", CFOPViewSet, basename="cfop-legacy")
router.register(r"tributos-spartacus", TributoSpartacusViewSet, basename="tributos-spartacus")

urlpatterns = router.urls + [

]
