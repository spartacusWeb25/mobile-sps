# Localidades/web/views/estados_views.py

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.utils import get_licenca_db_config
from localidades.models import Estados
from localidades.services.ibge_service import IBGEService, IBGEServiceError
from localidades.web.forms import EstadosForm
from .base import (
    LocalidadeListView,
    LocalidadeCreateView,
    LocalidadeUpdateView,
    LocalidadeDeleteView,
)


class EstadosListView(LocalidadeListView):
    model = Estados
    template_name = "Localidades/estados_list.html"
    context_object_name = "estados"
    campo_busca_nome = "esta_nome"


class EstadosCreateView(LocalidadeCreateView):
    model = Estados
    form_class = EstadosForm
    template_name = "Localidades/estados_form.html"
    url_lista = "LocalidadesWeb:estados_listar"
    mensagem_sucesso = "Estado criado com sucesso."


class EstadosUpdateView(LocalidadeUpdateView):
    model = Estados
    form_class = EstadosForm
    template_name = "Localidades/estados_form.html"
    url_lista = "LocalidadesWeb:estados_listar"
    mensagem_sucesso = "Estado atualizado com sucesso."


class EstadosDeleteView(LocalidadeDeleteView):
    model = Estados
    url_lista = "LocalidadesWeb:estados_listar"
    mensagem_sucesso = "Estado excluído com sucesso."


@require_POST
def sincronizar_estados_ibge(request, slug):
    """Importa/atualiza as 27 UFs a partir da API do IBGE."""
    banco = get_licenca_db_config(request) or "default"

    try:
        resultado = IBGEService.sincronizar_estados(banco)
        messages.success(
            request,
            f"Estados sincronizados com o IBGE: "
            f"{resultado['criados']} criados, {resultado['atualizados']} atualizados.",
        )
    except IBGEServiceError as exc:
        messages.error(request, str(exc))

    return redirect(reverse("LocalidadesWeb:estados_listar", kwargs={"slug": slug}))
