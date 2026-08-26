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
from processos.models import ChecklistModelo, ChecklistItem
from processos.services.checklist_service import ChecklistService
from processos.services.processo_service import ProcessoService
from processos.web.forms import (
    ChecklistModeloForm,
    ProcessoForm,
)
import json
from django.http import JsonResponse
from django.db import transaction

import logging
logger = logging.getLogger(__name__)

class _BaseProcessoFormView(FormView):
    def _ctx(self):
        for key, value in self.request.session.items():
            print(f"{key} => {value}")
        slug = self.kwargs.get("slug")
        return {
            "slug": slug,
            "db_alias": get_db_from_slug(slug) if slug else "default",
            "empresa": self.request.session.get("empresa_id"),
            "filial": self.request.session.get("filial_id"),
            "usuario_id": self.request.session.get("usua_codi"),
        }


class ChecklistModeloCreateView(_BaseProcessoFormView):
    template_name = "processos/modelo_create.html"
    form_class = ChecklistModeloForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cfg = self._ctx()
        context["modelos"] = ChecklistModelo.objects.using(cfg["db_alias"]).filter(
            chmo_empr=cfg["empresa"], chmo_fili=cfg["filial"]
        )
        return context

    def form_valid(self, form):
        cfg = self._ctx()
        itens_raw = self.request.POST.get("itens_json", "[]")
        itens_data = json.loads(itens_raw)
        if len(itens_data) == 0:
            messages.error(self.request, "Modelo faltando itens")
            return self.form_invalid(form)
        try:
            with transaction.atomic(using=cfg["db_alias"]):
                modelo = ChecklistService.criar_modelo(
                    db_alias=cfg["db_alias"],
                    empresa=cfg["empresa"],
                    filial=cfg["filial"],
                    nome=form.cleaned_data["nome"],
                    ativo=form.cleaned_data.get("ativo", True),
                )

                for item in itens_data:
                    if item.get("descricao"):
                        ChecklistService.criar_item(
                            db_alias=cfg["db_alias"],
                            empresa=cfg["empresa"],
                            filial=cfg["filial"],
                            modelo=modelo,
                            descricao=item["descricao"],
                            obrigatorio=item["obrigatorio"],
                        )
            messages.success(self.request, "Modelo de checklist criado com sucesso.")
            return redirect("processos:templates", slug=cfg["slug"])

        except Exception as e:
            messages.error(self.request, f"Erro ao salvar modelo: {str(e)}")
            return self.form_invalid(form)


class ChecklistItemCreateView(_BaseProcessoFormView):
    template_name = "processos/item_create.html"

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

class ModeloEditView(_BaseProcessoFormView):
    def post(self, request, slug, *args, **kwargs):
        cfg = self._ctx()
        data = json.loads(request.body)
        modelo_id = kwargs["modelo_id"]
        itens = data.get("itens", [])
        if len(itens) == 0:
            messages.error(request, "Modelo deve conter itens")
            return JsonResponse({"success": False})
        modelo = ChecklistModelo.objects.using(cfg["db_alias"]).get(
            chmo_empr = cfg["empresa"],
            chmo_fili = cfg["filial"],
            id = modelo_id
        )
        itens_antigos = ChecklistItem.objects.using(cfg["db_alias"]).filter(
            chit_empr=cfg["empresa"],
            chit_fili=cfg["filial"],
            chit_mode=modelo
        )
        descricoes = set(item["descricao"].strip() for item in itens)
        itens_antigos.exclude(chit_desc__in=descricoes).delete()
        for item in itens:
            ChecklistService.criar_ou_atualizar_item(
                db_alias=cfg["db_alias"],
                empresa=cfg["empresa"],
                filial=cfg["filial"],
                modelo=modelo,
                descricao=item["descricao"],
                obrigatorio=item["obrigatorio"],
            )
        return JsonResponse({"success": True})

class ProcessoCreateView(_BaseProcessoFormView):
    template_name = "processos/processo_create.html"
    form_class = ProcessoForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cfg = self._ctx()
        context["modelos"] = ChecklistModelo.objects.using(cfg["db_alias"]).filter(
            chmo_empr=cfg["empresa"], chmo_fili=cfg["filial"]
        )
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        cfg = self._ctx()
        kwargs["modelos"] = ProcessoService.listar_modelos(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
        )
        kwargs["os"] = ProcessoService.listar_os_sem_processo(
            db_alias = cfg["db_alias"],
            empresa = cfg["empresa"],
            filial = cfg["filial"]
        )
        kwargs["db_alias"] = cfg["db_alias"]
        kwargs["empresa"] = cfg["empresa"]
        return kwargs

    def form_valid(self, form):
        cfg = self._ctx()
        processo = ProcessoService.criar(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            modelo_id=form.cleaned_data["proc_mode"].id,
            descricao=form.cleaned_data["proc_desc"],
            os = form.cleaned_data["proc_os"],
            usuario_id=cfg["usuario_id"],
        )
        messages.success(self.request, "Processo criado e checklist inicializado.")
        return redirect("processos:detalhe", slug=cfg["slug"], pk=processo.id)

class ModeloToggleAtivoView(_BaseProcessoFormView):
    def post(self, request, slug, *args, **kwargs):
        cfg = self._ctx()
        modelo_id = kwargs["modelo_id"]
        ChecklistService.alternar_status_modelo(cfg["db_alias"], cfg["empresa"], cfg["filial"], modelo_id)
        messages.success(self.request, "Status do modelo atualizado.")
        return redirect("processos:templates", slug=cfg["slug"])
        