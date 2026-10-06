from .Views.listView import OcorrenciaListView, PerfilOcorrenciaListView
from .Views.createView import OcorrenciaCreateView, PerfilOcorrenciaCreateView, PerfilOcorrenciaUpdateView, PerfilOcorrenciaToggleView
from django.urls import path

app_name = "ocorrencias"

urlpatterns = [
    path("", OcorrenciaListView.as_view(), name="ocorrencias"),
    path("criar/", OcorrenciaCreateView.as_view(), name="ocorrencia_criar"),
    path("perfis/", PerfilOcorrenciaListView.as_view(), name="perfis"),
    path("perfis/criar/", PerfilOcorrenciaCreateView.as_view(), name="perfil_criar"),
    path("perfis/<int:pk>/", PerfilOcorrenciaUpdateView.as_view(), name="perfil_editar"),
    path("perfis/<int:pk>/toggle_ativar", PerfilOcorrenciaToggleView.as_view(), name="perfil_toggle_ativar")
]

