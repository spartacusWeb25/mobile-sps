from django.urls import path

from planogerencial.web.views.atualizar import PlanoGerencialInativarView
from planogerencial.web.views.criar import PlanoGerencialCriarView, MascaraGerencialCriarView
from planogerencial.web.views.editar import PlanoGerencialEditarView, MascaraGerencialEditarView
from planogerencial.web.views.listar import PlanoGerencialListView, MascaraGerencialListView

app_name = "planogerencial"

urlpatterns = [
    path("planos/", PlanoGerencialListView.as_view(), name="plano_listar"),
    path("planos/criar/", PlanoGerencialCriarView.as_view(), name="plano_criar"),
    path("<int:redu>/editar/", PlanoGerencialEditarView.as_view(), name="plano_editar"),
    path("<int:redu>/inativar/", PlanoGerencialInativarView.as_view(), name="plano_inativar"),

    path("planos/mascara/criar/", MascaraGerencialCriarView.as_view(), name="mascara_criar"),
    path("planos/mascara/<int:pk>/editar/", MascaraGerencialEditarView.as_view(), name="mascara_editar"),
    path("planos/mascara/", MascaraGerencialListView.as_view(), name="mascara_listar"),
]