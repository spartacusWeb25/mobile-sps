from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView

from planogerencial.web.forms import (
    PlanoGerencialMascaraForm,
    PlanoGerencialForm,
    PlanoGerencialEditarForm,
)
from planogerencial.web.views.contexto import PlanoGerencialContextMixin
from planogerencial.services.plano_service import PlanoGerencialService
from planogerencial.services.mascara_service import MascaraGerencialService


class PlanoGerencialBaseFormView(PlanoGerencialContextMixin, FormView):
    """
    Base para garantir contexto padrão em todos os templates.
    Evita slug vazio no {% url %}.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["slug"] = self.get_slug()
        context["empresa"] = self.get_empresa()
        context["db_alias"] = self.get_db_alias()
        return context


class PlanoGerencialCriarView(PlanoGerencialBaseFormView):
    template_name = "planogerencial/plano_form.html"
    form_class = PlanoGerencialForm

    def get_service(self):
        return PlanoGerencialService(
            db_alias=self.get_db_alias(),
            empresa=self.get_empresa(),
        )

    def form_valid(self, form):
        service = self.get_service()

        try:
            service.criar(
                nome=form.cleaned_data["nome"],
                parent_redu=form.cleaned_data.get("parent_redu"),
            )
            messages.success(self.request, "Conta gerencial criada com sucesso.")

        except Exception as e:
            messages.error(self.request, str(e))

        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy(
            "planogerencial:plano_listar",
            kwargs={"slug": self.get_slug()},
        )


class MascaraGerencialCriarView(PlanoGerencialBaseFormView):
    template_name = "planogerencial/mascara_form.html"
    form_class = PlanoGerencialMascaraForm

    def get_service(self):
        return MascaraGerencialService(
            db_alias=self.get_db_alias(),
            empresa=self.get_empresa(),
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["empresa"] = self.get_empresa()
        return kwargs

    def form_valid(self, form):
        db_alias = self.get_db_alias()

        try:
            obj = form.save(commit=False)
            obj.gere_empr = self.get_empresa()
            obj.save(using=db_alias)

            messages.success(self.request, "Máscara gerencial salva com sucesso.")

        except Exception as e:
            messages.error(self.request, str(e))

        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy(
            "planogerencial:plano_listar",
            kwargs={"slug": self.get_slug()},
        )