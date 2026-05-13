from django.contrib import messages
from django.shortcuts import redirect
try:
    from django.utils.http import url_has_allowed_host_and_scheme
except Exception:
    from django.utils.http import is_safe_url as _is_safe_url

    def url_has_allowed_host_and_scheme(url, allowed_hosts=None, require_https=False):
        return _is_safe_url(url=url, allowed_hosts=allowed_hosts, require_https=require_https)
from django.views.generic import FormView

from core.utils import get_db_from_slug
from processos.models import ChecklistModelo, ProcessoTipo
from processos.services.checklist_service import ChecklistService
from processos.services.processo_service import ProcessoService
from processos.web.forms import (
    ChecklistItemForm,
    ChecklistModeloForm,
    ProcessoForm,
    ProcessoTipoForm,
)


class _BaseProcessoFormView(FormView):
    def _ctx(self):
        slug = self.kwargs.get("slug")
        return {
            "slug": slug,
            "db_alias": get_db_from_slug(slug) if slug else "default",
            "empresa": self.request.session.get("empresa_id", 1),
            "filial": self.request.session.get("filial_id", 1),
            "usuario_id": self.request.session.get("usuario_id"),
        }


class ProcessoTipoCreateView(_BaseProcessoFormView):
    template_name = "processos/tipo_create.html"
    form_class = ProcessoTipoForm

    def form_valid(self, form):
        cfg = self._ctx()
        ProcessoService.criar_tipo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            nome=form.cleaned_data["nome"],
            codigo=form.cleaned_data["codigo"],
            ativo=form.cleaned_data.get("ativo", True),
        )
        messages.success(self.request, "Tipo de processo criado com sucesso.")
        return redirect("processos:templates", slug=cfg["slug"])


class ChecklistModeloCreateView(_BaseProcessoFormView):
    template_name = "processos/modelo_create.html"
    form_class = ChecklistModeloForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cfg = self._ctx()
        context["tipos"] = ProcessoService.listar_tipos(
            db_alias=cfg["db_alias"], empresa=cfg["empresa"], filial=cfg["filial"]
        )
        return context

    def form_valid(self, form):
        cfg = self._ctx()
        tipo = ProcessoTipo.objects.using(cfg["db_alias"]).get(
            id=form.cleaned_data["processo_tipo_id"],
            prot_empr=cfg["empresa"],
            prot_fili=cfg["filial"],
        )
        ChecklistService.criar_modelo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo_tipo=tipo,
            nome=form.cleaned_data["nome"],
            versao=form.cleaned_data["versao"],
            ativo=form.cleaned_data.get("ativo", True),
        )
        messages.success(self.request, "Modelo de checklist criado com sucesso.")
        return redirect("processos:templates", slug=cfg["slug"])


class ChecklistItemCreateView(_BaseProcessoFormView):
    template_name = "processos/item_create.html"
    form_class = ChecklistItemForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cfg = self._ctx()
        context["modelos"] = ChecklistModelo.objects.using(cfg["db_alias"]).filter(
            chmo_empr=cfg["empresa"], chmo_fili=cfg["filial"]
        )
        modelo_id = self.request.GET.get("modelo_id")
        context["selected_modelo_id"] = (
            int(modelo_id) if modelo_id and modelo_id.isdigit() else None
        )
        context["next_url"] = self.request.GET.get("next") or self.request.POST.get(
            "next"
        )
        return context

    def form_valid(self, form):
        cfg = self._ctx()
        modelo = ChecklistModelo.objects.using(cfg["db_alias"]).get(
            id=form.cleaned_data["checklist_modelo_id"],
            chmo_empr=cfg["empresa"],
            chmo_fili=cfg["filial"],
        )
        ChecklistService.criar_item(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            modelo=modelo,
            descricao=form.cleaned_data["descricao"],
            ordem=form.cleaned_data["ordem"],
            obrigatorio=form.cleaned_data.get("obrigatorio", True),
        )
        messages.success(self.request, "Item de checklist criado com sucesso.")
        next_url = self.request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return redirect(next_url)
        return redirect("processos:templates", slug=cfg["slug"])


class ProcessoCreateView(_BaseProcessoFormView):
    template_name = "processos/processo_create.html"
    form_class = ProcessoForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        cfg = self._ctx()
        kwargs["tipos"] = ProcessoService.listar_tipos(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
        )
        return kwargs

    def form_valid(self, form):
        cfg = self._ctx()
        processo = ProcessoService.criar(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            tipo_id=form.cleaned_data["proc_tipo"].id,
            descricao=form.cleaned_data["proc_desc"],
            usuario_id=cfg["usuario_id"],
        )
        messages.success(self.request, "Processo criado e checklist inicializado.")
        return redirect("processos:detalhe", slug=cfg["slug"], pk=processo.id)
