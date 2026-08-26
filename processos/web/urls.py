from django.urls import path

from .views.create import (
    ChecklistItemCreateView,
    ChecklistModeloCreateView,
    ProcessoCreateView,
    ModeloEditView,
    ModeloToggleAtivoView
)
from .views.delete import ProcessoDeleteView
from .views.detail import ProcessoDetailView
from .views.list import ProcessoListView, ProcessoTemplateNavView
from .views.savechecklist import (
    SalvarChecklistView,
    SincronizarChecklistView,
    ValidarProcessoView
)

app_name = "processos"

urlpatterns = [
    path("", ProcessoListView.as_view(), name="lista"),
    path("templates/", ProcessoTemplateNavView.as_view(), name="templates"),
    path(
        "templates/novo/",
        ChecklistModeloCreateView.as_view(),
        name="modelo_criar",
    ),
    path("templates/itens/novo/", ChecklistItemCreateView.as_view(), name="item_criar"),
    path("templates/<int:modelo_id>/editar/", ModeloEditView.as_view(),name="modelo_editar"),
    path("templates/<int:modelo_id>/toggle_ativo/", ModeloToggleAtivoView.as_view(),name="modelo_toggle_ativo"),
    path("criar/", ProcessoCreateView.as_view(), name="criar"),
    path("<int:pk>/", ProcessoDetailView.as_view(), name="detalhe"),
    path("<int:pk>/delete/", ProcessoDeleteView.as_view(), name="excluir"),
    path(
        "<int:pk>/checklist/salvar/",
        SalvarChecklistView.as_view(),
        name="salvar_checklist",
    ),
    path(
        "<int:pk>/checklist/sincronizar/",
        SincronizarChecklistView.as_view(),
        name="sincronizar_checklist",
    ),
    path("<int:pk>/validar/", ValidarProcessoView.as_view(), name="validar"),
]
