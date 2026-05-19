from django.views.generic import ListView, DetailView, CreateView, View
from django.shortcuts import redirect
from django.contrib import messages
from core.utils import get_db_from_slug
from devolucoes_pisos.models import Creditotrocas
from devolucoes_pisos.services.creditos_service import CreditosService, DadosService


class CreditosListView(ListView):
    model = Creditotrocas
    context_object_name = "creditos"
    template_name = "creditos/list.html"
    
    def get_queryset(self):
        self.slug = self.kwargs.get("slug")
        self.banco = get_db_from_slug(self.slug)
        return CreditosService.listar(
            banco=self.banco,
            empresa=self.request.session.get("empresa_id"),
            filial=self.request.session.get("filial_id"),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        slug = self.kwargs.get("slug")
        banco = get_db_from_slug(slug)

        empresa_atual = self.request.session.get("empresa_id")
        filial_atual = self.request.session.get("filial_id")

        context["slug"] = slug
        context["empresa"] = empresa_atual
        context["filial"] = filial_atual
        context["empresas"] = DadosService.listar_empresas(banco=banco)
        context["filiais"] = DadosService.listar_filiais(
            banco=banco,
            empresa=empresa_atual,
        )

        return context


class CreditosDetailView(DetailView):
    model = Creditotrocas
    context_object_name = "credito"
    template_name = "creditos/detail.html"

    def get_object(self):
        self.slug = self.kwargs.get("slug")
        self.banco = get_db_from_slug(self.slug)
        return CreditosService.buscar_por_id(
            banco=self.banco,
            empresa=self.request.session.get("empresa_id"),
            filial=self.request.session.get("filial_id"),
            credito_id=self.kwargs["pk"],
        )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["slug"] = self.kwargs.get("slug")
        context["filial"] = self.request.session.get("filial_id") or self.request.session.get("fili") or 1
        context["empresa"] = self.request.session.get("empresa_id") or self.request.session.get("empr") or 1
        return context


class CreditosCreateView(CreateView):
    model = Creditotrocas
    fields = [
        "cred_fina_clie",
        "cred_fina_vend",
        "cred_fina_data",
        "cred_fina_es",
        "cred_fina_valo",
        "cred_fina_obse",
    ]
    context_object_name = "credito"
    template_name = "creditos/create.html"
    success_url = "/creditos/"
    
    def form_valid(self, form):
        self.slug = self.kwargs.get("slug")
        self.banco = get_db_from_slug(self.slug)
        form.instance.cred_fina_banc = self.banco
        form.instance.cred_fina_empr = self.request.session.get("empresa_id") or self.request.session.get("empr") or 1
        form.instance.cred_fina_fili = self.request.session.get("filial_id") or self.request.session.get("fili") or 1
        return super().form_valid(form)
    
    
class CreditosTransferirView(View):
    def post(self, request, slug, pk):
        banco = get_db_from_slug(slug)

        empresa_destino = request.POST.get("empresa_destino")
        filial_destino = request.POST.get("filial_destino")
        observacao = request.POST.get("observacao")

        try:
            CreditosService.transferir_entre_empresa_filial(
                banco=banco,
                credito_id=pk,
                empresa_origem=request.session.get("empresa_id") or request.session.get("empr") or 1,
                filial_origem=request.session.get("filial_id") or request.session.get("fili") or 1,
                empresa_destino=empresa_destino,
                filial_destino=filial_destino,
                observacao=observacao,
            )

            messages.success(request, "Crédito transferido com sucesso.")

        except ValueError as e:
            messages.error(request, str(e))

        return redirect("DevolucoesPisosWeb:creditos_listar", slug=slug)