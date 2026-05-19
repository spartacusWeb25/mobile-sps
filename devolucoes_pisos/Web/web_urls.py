from django.urls import path

from devolucoes_pisos.Web.Views.createView import DevolucaoPisosCreateView
from devolucoes_pisos.Web.Views.listView import DevolucoesPisosListView
from devolucoes_pisos.Web.Views.updateView import DevolucaoPisosUpdateView
from ..Web.Views.creditos import CreditosCreateView, CreditosListView, CreditosDetailView, CreditosTransferirView



app_name = "DevolucoesPisosWeb"

urlpatterns = [
    path("", DevolucoesPisosListView.as_view(), name="devolucoes_pisos_listar"),
    path("criar/", DevolucaoPisosCreateView.as_view(), name="devolucao_pisos_criar"),
    path("<int:pk>/editar/", DevolucaoPisosUpdateView.as_view(), name="devolucao_pisos_editar"),
    path("creditos/", CreditosCreateView.as_view(), name="creditos_criar"),
    path("creditos/listar/", CreditosListView.as_view(), name="creditos_listar"),
    path("creditos/<int:pk>/detalhar/", CreditosDetailView.as_view(), name="creditos_detalhar"),
    path("creditos/<int:pk>/transferir/", CreditosTransferirView.as_view(), name="creditos_transferir"),
]

