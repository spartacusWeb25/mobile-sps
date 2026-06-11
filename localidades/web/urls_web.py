# Localidades/web/urls_web.py

from django.urls import path

from .views.estados_views import (
    EstadosListView,
    EstadosCreateView,
    EstadosUpdateView,
    EstadosDeleteView,
    sincronizar_estados_ibge,
)
from .views.paises_views import (
    PaisesListView,
    PaisesCreateView,
    PaisesUpdateView,
    PaisesDeleteView,
    sincronizar_paises_ibge,
)
from .views.cidades_views import (
    CidadesListView,
    CidadesCreateView,
    CidadesUpdateView,
    CidadesDeleteView,
    importar_cidade_ibge,
)

app_name = "LocalidadesWeb"

urlpatterns = [
    # ----- Estados -----
    path("estados/", EstadosListView.as_view(), name="estados_listar"),
    path("estados/novo/", EstadosCreateView.as_view(), name="estados_criar"),
    path("estados/<int:pk>/editar/", EstadosUpdateView.as_view(), name="estados_editar"),
    path("estados/<int:pk>/excluir/", EstadosDeleteView.as_view(), name="estados_excluir"),
    path("estados/sincronizar-ibge/", sincronizar_estados_ibge, name="estados_sincronizar_ibge"),

    # ----- Países -----
    path("paises/", PaisesListView.as_view(), name="paises_listar"),
    path("paises/novo/", PaisesCreateView.as_view(), name="paises_criar"),
    path("paises/<int:pk>/editar/", PaisesUpdateView.as_view(), name="paises_editar"),
    path("paises/<int:pk>/excluir/", PaisesDeleteView.as_view(), name="paises_excluir"),
    path("paises/sincronizar-ibge/", sincronizar_paises_ibge, name="paises_sincronizar_ibge"),

    # ----- Cidades -----
    path("cidades/", CidadesListView.as_view(), name="cidades_listar"),
    path("cidades/nova/", CidadesCreateView.as_view(), name="cidades_criar"),
    path("cidades/<int:pk>/editar/", CidadesUpdateView.as_view(), name="cidades_editar"),
    path("cidades/<int:pk>/excluir/", CidadesDeleteView.as_view(), name="cidades_excluir"),
    path("cidades/importar-ibge/", importar_cidade_ibge, name="cidades_importar_ibge"),
]
