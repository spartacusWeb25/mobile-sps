from django.urls import path

from .views.create import (
    ChecklistItemCreateView,
    ChecklistModeloCreateView,
    ProcessoCreateView,
    ProcessoTipoCreateView,
)
from .views.delete import ProcessoDeleteView
from .views.detail import ProcessoDetailView, ProcessoAbrirOSView, ProcessoAtualizarClienteView, autocomplete_entidades
from .views.list import ProcessoListView, ProcessoTemplateNavView
from .views.savechecklist import (
    SalvarChecklistView,
    SincronizarChecklistView,
    ValidarProcessoView,
)

app_name = "processos"

urlpatterns = [
    path("", ProcessoListView.as_view(), name="lista"),
    path("autocompletes/entidades/", autocomplete_entidades, name="autocomplete_entidades"),
    path("templates/", ProcessoTemplateNavView.as_view(), name="templates"),
    path("templates/tipos/novo/", ProcessoTipoCreateView.as_view(), name="tipo_criar"),
    path(
        "templates/modelos/novo/",
        ChecklistModeloCreateView.as_view(),
        name="modelo_criar",
    ),
    path("templates/itens/novo/", ChecklistItemCreateView.as_view(), name="item_criar"),
    path("criar/", ProcessoCreateView.as_view(), name="criar"),
    path("<int:pk>/", ProcessoDetailView.as_view(), name="detalhe"),
    path("<int:pk>/cliente/", ProcessoAtualizarClienteView.as_view(), name="atualizar_cliente"),
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
    path("<int:pk>/abrir_os/", ProcessoAbrirOSView.as_view(), name="abrir_os"),
]
