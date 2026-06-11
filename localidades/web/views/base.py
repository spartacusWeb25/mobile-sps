# Localidades/web/views/base.py

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from core.mixin import DBAndSlugMixin


class LocalidadeListView(DBAndSlugMixin, ListView):
    """ListView base: multibanco + busca por nome + paginação."""

    paginate_by = 20
    campo_busca_nome = None  # ex: 'esta_nome'

    def get_queryset(self):
        qs = self.model.objects.using(self.db_alias).all()

        busca = (self.request.GET.get("q") or "").strip()
        if busca and self.campo_busca_nome:
            qs = qs.filter(**{f"{self.campo_busca_nome}__icontains": busca})

        return qs.order_by(self.campo_busca_nome or "pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = (self.request.GET.get("q") or "").strip()
        return context


class LocalidadeFormMixin(DBAndSlugMixin):
    """Create/Update base: salva no banco da licença e ajusta FKs."""

    url_lista = None  # ex: 'LocalidadesWeb:estados_listar'
    mensagem_sucesso = "Registro salvo com sucesso."

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Forms com FK precisam apontar para o banco correto
        if hasattr(form, "set_banco"):
            form.set_banco(self.db_alias)
        return form

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save(using=self.db_alias)
        messages.success(self.request, self.mensagem_sucesso)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.url_lista, kwargs={"slug": self.slug})


class LocalidadeCreateView(LocalidadeFormMixin, CreateView):
    pass


class LocalidadeUpdateView(LocalidadeFormMixin, UpdateView):

    def get_queryset(self):
        return self.model.objects.using(self.db_alias).all()


class LocalidadeDeleteView(DBAndSlugMixin, DeleteView):

    url_lista = None
    mensagem_sucesso = "Registro excluído com sucesso."
    template_name = "localidades/confirmar_exclusao.html"   

    def get_queryset(self):
        return self.model.objects.using(self.db_alias).all()

    def form_valid(self, form):
        self.object = self.get_object()
        try:
            self.object.delete(using=self.db_alias)
            messages.success(self.request, self.mensagem_sucesso)
        except Exception as exc:
            messages.error(
                self.request,
                f"Não foi possível excluir: o registro pode estar em uso. ({exc})",
            )
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.url_lista, kwargs={"slug": self.slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["url_lista"] = self.url_lista
        return context
