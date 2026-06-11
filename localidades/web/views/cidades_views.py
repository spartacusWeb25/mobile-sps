# Localidades/web/views/cidades_views.py

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from core.utils import get_licenca_db_config
from localidades.models import Cidades
from localidades.services.ibge_service import IBGEService, IBGEServiceError
from localidades.web.forms import CidadesForm, ImportarCidadeIBGEForm
from .base import (
    LocalidadeListView,
    LocalidadeCreateView,
    LocalidadeUpdateView,
    LocalidadeDeleteView,
)


class CidadesListView(LocalidadeListView):
    model = Cidades
    template_name = "Localidades/cidades_list.html"
    context_object_name = "cidades"
    campo_busca_nome = "cida_nome"

    def get_queryset(self):
        qs = super().get_queryset().select_related("cida_esta", "cida_pais")

        uf = (self.request.GET.get("uf") or "").strip().upper()
        if uf:
            qs = qs.filter(cida_sigl=uf)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["uf"] = (self.request.GET.get("uf") or "").strip().upper()
        context["form_ibge"] = ImportarCidadeIBGEForm()
        return context


class CidadesCreateView(LocalidadeCreateView):
    model = Cidades
    form_class = CidadesForm
    template_name = "Localidades/cidades_form.html"
    url_lista = "LocalidadesWeb:cidades_listar"
    mensagem_sucesso = "Cidade criada com sucesso."


class CidadesUpdateView(LocalidadeUpdateView):
    model = Cidades
    form_class = CidadesForm
    template_name = "Localidades/cidades_form.html"
    url_lista = "LocalidadesWeb:cidades_listar"
    mensagem_sucesso = "Cidade atualizada com sucesso."


class CidadesDeleteView(LocalidadeDeleteView):
    model = Cidades
    url_lista = "LocalidadesWeb:cidades_listar"
    mensagem_sucesso = "Cidade excluída com sucesso."


def importar_cidade_ibge(request, slug):
    """
    Importa uma cidade pelo código IBGE do município.
    Cria estado e país automaticamente se ainda não existirem.
    """
    destino = reverse("LocalidadesWeb:cidades_listar", kwargs={"slug": slug})

    if request.method != "POST":
        return redirect(destino)

    banco = get_licenca_db_config(request) or "default"
    form = ImportarCidadeIBGEForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Informe um código IBGE válido.")
        return redirect(destino)

    try:
        cidade, criada = IBGEService.obter_ou_criar_cidade(
            banco=banco,
            codigo_ibge=form.cleaned_data["codigo_ibge"],
        )
        if criada:
            messages.success(
                request,
                f"Cidade '{cidade.cida_nome} - {cidade.cida_sigl}' importada do IBGE.",
            )
        else:
            messages.info(
                request,
                f"Cidade '{cidade.cida_nome} - {cidade.cida_sigl}' já estava cadastrada.",
            )
    except IBGEServiceError as exc:
        messages.error(request, str(exc))

    return redirect(destino)
