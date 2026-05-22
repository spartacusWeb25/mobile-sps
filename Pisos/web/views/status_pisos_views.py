# Pisos/web/views/status_pisos_views.py

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.shortcuts import redirect

from core.utils import get_db_from_slug
from Pisos.models import StatusPisos
from Pisos.web.forms import StatusPisosForm
from Pisos.services.status_pisos_seed_service import StatusPisosSeedService
from Pisos.services.status_criar import StatusCriar


class StatusPisosBaseMixin:
    model = StatusPisos
    form_class = StatusPisosForm

    def get_slug(self):
        return self.kwargs.get("slug")

    def get_banco(self):
        return get_db_from_slug(self.get_slug())

    def get_empresa(self):
        return self.request.session.get("empresa_id", 1)

    def get_filial(self):
        return self.request.session.get("filial_id", 1)

    def get_success_url(self):
        return reverse_lazy("PisosWeb:status_pisos_listar", kwargs={
            "slug": self.get_slug()
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['slug'] = self.get_slug()
        return ctx


class StatusPisosListView(StatusPisosBaseMixin, ListView):
    template_name = "pisos/status_pisos/listar.html"
    context_object_name = "status"

    def get_queryset(self):
        qs = StatusPisos.objects.using(self.get_banco()).filter(
            stat_empr=self.get_empresa(),
            stat_fili=self.get_filial(),
        )
        

        tipo = self.request.GET.get("tipo")
        ativo = self.request.GET.get("ativo")

        if tipo in ["0", "1"]:
            qs = qs.filter(stat_tipo=tipo)

        if ativo in ["0", "1"]:
            qs = qs.filter(stat_ativo=bool(int(ativo)))

        return qs.order_by("stat_tipo", "stat_codigo")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["slug"] = self.get_slug()
        ctx["tipo"] = self.request.GET.get("tipo", "")
        ctx["ativo"] = self.request.GET.get("ativo", "")
        return ctx


class StatusPisosCreateView(StatusPisosBaseMixin, CreateView):
    template_name = "pisos/status_pisos/form.html"

    def form_valid(self, form):
        form.instance.stat_empr = self.get_empresa()
        form.instance.stat_fili = self.get_filial()

        last = StatusPisos.objects.using(self.get_banco()).filter(
            stat_empr=self.get_empresa(),
            stat_fili=self.get_filial(),
        ).order_by("-stat_codigo").first()

        form.instance.stat_codigo = last.stat_codigo + 1 if last else 1

        form.instance.save(using=self.get_banco())

        messages.success(self.request, "Status criado com sucesso.")
        StatusCriar.status_orcamentos_criar(self.get_banco(), self.get_empresa(), self.get_filial())
        StatusCriar.status_pedidos_criar(self.get_banco(), self.get_empresa(), self.get_filial())
        return redirect(self.get_success_url())


class StatusPisosUpdateView(StatusPisosBaseMixin, UpdateView):
    template_name = "pisos/status_pisos/form.html"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return StatusPisos.objects.using(self.get_banco()).filter(
            stat_empr=self.get_empresa(),
            stat_fili=self.get_filial(),
        )

    def form_valid(self, form):
        form.instance.save(using=self.get_banco())
        messages.success(self.request, "Status atualizado com sucesso.")
        return redirect(self.get_success_url())


class StatusPisosDeleteView(StatusPisosBaseMixin, DeleteView):
    template_name = "pisos/status_pisos/confirmar_exclusao.html"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return StatusPisos.objects.using(self.get_banco()).filter(
            stat_empr=self.get_empresa(),
            stat_fili=self.get_filial(),
        )

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Status removido com sucesso.")
        return super().delete(request, *args, **kwargs)


def criar_status_padrao_view(request, slug):
    banco = get_db_from_slug(slug)
    empr = request.session.get("empresa_id", 1)
    fili = request.session.get("filial_id", 1)

    StatusPisosSeedService.criar_padrao(banco, empr, fili)

    messages.success(request, "Status padrão criados com sucesso.")
    return redirect("PisosWeb:status_pisos_listar", slug=slug)
