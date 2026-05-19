from django.views.generic import UpdateView
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect
from ..forms import PlanoGerencialForm, PlanoGerencialMascaraForm
from ...models import PlanoGerencialMascara, PlanoGerencialConta
from .contexto import PlanoGerencialContextMixin
class PlanoGerencialEditarView(PlanoGerencialContextMixin, UpdateView):
    model = PlanoGerencialConta
    form_class = PlanoGerencialForm
    template_name = "planogerencial/plano_form.html"
    pk_url_kwarg = "redu"

    def get_queryset(self):
        return (
            PlanoGerencialConta.objects.using(self.get_db_alias())
            .filter(gere_empr=self.get_empresa())
        )

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        return queryset.get(gere_redu=self.kwargs["redu"])

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.save(using=self.get_db_alias())

        messages.success(self.request, "Conta gerencial atualizada com sucesso.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy(
            "planogerencial:plano_listar",
            kwargs={"slug": self.get_slug()},
        )




class MascaraGerencialEditarView(PlanoGerencialContextMixin, UpdateView):
    model = PlanoGerencialMascara
    form_class = PlanoGerencialMascaraForm
    template_name = "planogerencial/mascara_form.html"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return PlanoGerencialMascara.objects.using(self.get_db_alias()).filter(
            gere_empr=self.get_empresa()
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["empresa"] = self.get_empresa()
        return kwargs

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.gere_empr = self.get_empresa()
        obj.save(using=self.get_db_alias())

        messages.success(self.request, "Máscara gerencial atualizada com sucesso.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy(
            "planogerencial:plano_listar",
            kwargs={"slug": self.get_slug()},
        )