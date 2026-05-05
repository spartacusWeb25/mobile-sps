from django.urls import path

from devolucoes_pisos.Web.Views.createView import DevolucaoPisosCreateView
from devolucoes_pisos.Web.Views.listView import DevolucoesPisosListView
from devolucoes_pisos.Web.Views.updateView import DevolucaoPisosUpdateView

app_name = "DevolucoesPisosWeb"

urlpatterns = [
    path("", DevolucoesPisosListView.as_view(), name="devolucoes_pisos_listar"),
    path("criar/", DevolucaoPisosCreateView.as_view(), name="devolucao_pisos_criar"),
    path("<int:pk>/editar/", DevolucaoPisosUpdateView.as_view(), name="devolucao_pisos_editar"),
]

