# Localidades/web/views/paises_views.py

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.utils import get_licenca_db_config
from localidades.models import Paises
from localidades.services.ibge_service import IBGEService, IBGEServiceError
from localidades.web.forms import PaisesForm
from .base import (
    LocalidadeListView,
    LocalidadeCreateView,
    LocalidadeUpdateView,
    LocalidadeDeleteView,
)


class PaisesListView(LocalidadeListView):
    model = Paises
    template_name = "localidades/paises_list.html"
    context_object_name = "paises"
    campo_busca_nome = "pais_nome"


class PaisesCreateView(LocalidadeCreateView):
    model = Paises
    form_class = PaisesForm
    template_name = "localidades/paises_form.html"
    url_lista = "localidadesWeb:paises_listar"
    mensagem_sucesso = "País criado com sucesso."


class PaisesUpdateView(LocalidadeUpdateView):
    model = Paises
    form_class = PaisesForm
    template_name = "localidades/paises_form.html"
    url_lista = "localidadesWeb:paises_listar"
    mensagem_sucesso = "País atualizado com sucesso."


class PaisesDeleteView(LocalidadeDeleteView):
    model = Paises
    url_lista = "localidadesWeb:paises_listar"
    mensagem_sucesso = "País excluído com sucesso."


@require_POST
def sincronizar_paises_ibge(request, slug):
    """Importa/atualiza todos os países a partir da API do IBGE."""
    banco = get_licenca_db_config(request) or "default"

    try:
        resultado = IBGEService.sincronizar_paises(banco)
        messages.success(
            request,
            f"Países sincronizados com o IBGE: "
            f"{resultado['criados']} criados, {resultado['atualizados']} atualizados.",
        )
    except IBGEServiceError as exc:
        messages.error(request, str(exc))

    return redirect(reverse("localidadesWeb:paises_listar", kwargs={"slug": slug}))
