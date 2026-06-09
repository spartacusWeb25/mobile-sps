from django.views.generic import ListView, DetailView, CreateView, View
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from datetime import date
from core.utils import get_db_from_slug
from devolucoes_pisos.models import Creditotrocas
from devolucoes_pisos.services.creditos_service import CreditosService, DadosService
from Entidades.models import Entidades


def autocomplete_clientes(request, slug=None):
    banco = get_db_from_slug(slug)
    empresa_id = request.session.get("empresa_id") or request.session.get("empr") or 1
    term = (request.GET.get("term") or request.GET.get("q") or "").strip()

    qs = Entidades.objects.using(banco).filter(
        enti_empr=str(empresa_id),
        enti_tipo_enti__in=["CL", "AM"],
        enti_situ="1",
    )
    if term:
        filtros = Q(enti_nome__icontains=term) | Q(enti_fant__icontains=term)
        if term.isdigit():
            filtros |= Q(enti_clie__icontains=term)
        qs = qs.filter(filtros)
    qs = qs.only("enti_clie", "enti_nome").order_by("enti_nome")[:20]
    return JsonResponse({"results": [{"id": str(obj.enti_clie), "text": f"{obj.enti_clie} - {obj.enti_nome}"} for obj in qs]})


def autocomplete_vendedores(request, slug=None):
    banco = get_db_from_slug(slug)
    empresa_id = request.session.get("empresa_id") or request.session.get("empr") or 1
    term = (request.GET.get("term") or request.GET.get("q") or "").strip()

    qs = Entidades.objects.using(banco).filter(
        enti_empr=str(empresa_id),
        enti_tipo_enti__in=["VE", "AM", "FU", "AR"],
        enti_situ="1",
    )
    if term:
        filtros = Q(enti_nome__icontains=term) | Q(enti_fant__icontains=term)
        if term.isdigit():
            filtros |= Q(enti_clie__icontains=term)
        qs = qs.filter(filtros)
    qs = qs.only("enti_clie", "enti_nome").order_by("enti_nome")[:20]
    return JsonResponse({"results": [{"id": str(obj.enti_clie), "text": f"{obj.enti_clie} - {obj.enti_nome}"} for obj in qs]})


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["slug"] = self.kwargs.get("slug")
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for nome, field in form.fields.items():
            css = "form-control"
            if nome == "cred_fina_obse":
                field.widget.attrs["rows"] = 3
            if nome == "cred_fina_data":
                field.widget.input_type = "date"
            field.widget.attrs["class"] = css
        form.fields["cred_fina_clie"].widget.input_type = "hidden"
        form.fields["cred_fina_vend"].widget.input_type = "hidden"
        form.fields["cred_fina_data"].initial = form.fields["cred_fina_data"].initial or date.today()
        form.fields["cred_fina_es"].initial = form.fields["cred_fina_es"].initial or 1
        form.fields["cred_fina_valo"].widget.attrs["step"] = "0.01"
        return form

    def get_success_url(self):
        return redirect("DevolucoesPisosWeb:creditos_listar", slug=self.kwargs.get("slug")).url
    
    def form_valid(self, form):
        self.slug = self.kwargs.get("slug")
        self.banco = get_db_from_slug(self.slug)
        empresa = self.request.session.get("empresa_id") or self.request.session.get("empr") or 1
        filial = self.request.session.get("filial_id") or self.request.session.get("fili") or 1

        clie = str(form.cleaned_data.get("cred_fina_clie") or "").strip()
        vend = str(form.cleaned_data.get("cred_fina_vend") or "").strip()

        if not clie.isdigit():
            form.add_error("cred_fina_clie", "Selecione um cliente válido na busca.")
        if not vend.isdigit():
            form.add_error("cred_fina_vend", "Selecione um vendedor válido na busca.")

        if clie.isdigit():
            existe_cliente = Entidades.objects.using(self.banco).filter(
                enti_empr=str(empresa),
                enti_clie=int(clie),
                enti_tipo_enti__in=["CL", "AM"],
                enti_situ="1",
            ).exists()
            if not existe_cliente:
                form.add_error("cred_fina_clie", "Cliente não encontrado ou inativo.")

        if vend.isdigit():
            existe_vendedor = Entidades.objects.using(self.banco).filter(
                enti_empr=str(empresa),
                enti_clie=int(vend),
                enti_tipo_enti__in=["VE", "AM", "FU", "AR"],
                enti_situ="1",
            ).exists()
            if not existe_vendedor:
                form.add_error("cred_fina_vend", "Vendedor não encontrado ou inativo.")

        valor = form.cleaned_data.get("cred_fina_valo")
        if valor in (None, ""):
            form.add_error("cred_fina_valo", "Informe o valor do crédito.")

        if form.errors:
            return self.form_invalid(form)

        form.instance.cred_fina_banc = self.banco
        form.instance.cred_fina_empr = int(empresa)
        form.instance.cred_fina_fili = int(filial)
        form.instance.cred_fina_clie = int(clie)
        form.instance.cred_fina_vend = int(vend)
        form.instance.cred_fina_es = int(form.cleaned_data.get("cred_fina_es") or 1)
        form.instance.cred_fina_data = form.cleaned_data.get("cred_fina_data") or date.today()
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
