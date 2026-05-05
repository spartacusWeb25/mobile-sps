import json

from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import CreateView

from core.utils import get_db_from_slug
from devolucoes_pisos.Web.forms import DevolucaoPedidoPisoForm
from devolucoes_pisos.services.troca_devolucao_service import DevolucaoPedidoPisoService


class DevolucaoPisosCreateView(CreateView):
    form_class = DevolucaoPedidoPisoForm
    template_name = "DevolucoesPisos/devolucao_form.html"

    def form_valid(self, form):
        slug = self.kwargs.get("slug")
        banco = get_db_from_slug(slug)

        usuario = self.request.session.get("usua_codi") or self.request.session.get("usuario") or None
        try:
            usuario = int(usuario) if usuario not in (None, "") else None
        except Exception:
            usuario = None

        itens_json = self.request.POST.get("itens_json") or "[]"
        try:
            itens = json.loads(itens_json)
        except Exception:
            itens = []

        try:
            self.object = DevolucaoPedidoPisoService.criar_ou_atualizar_por_pedido(
                banco=banco,
                pedido_numero=form.cleaned_data["devo_pedi"],
                usuario=usuario,
                tipo=form.cleaned_data.get("tipo") or "DEVO",
                desconto=form.cleaned_data.get("devo_desc"),
                data_devolucao=form.cleaned_data.get("devo_data"),
                itens=itens,
            )
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        messages.success(self.request, f"Troca/Devolução do pedido #{self.object.devo_pedi} salva com sucesso.")
        return redirect("DevolucoesPisosWeb:devolucoes_pisos_listar", slug=slug)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["slug"] = self.kwargs.get("slug")
        context["titulo"] = "Nova Troca/Devolução (Pisos)"
        context["empresa"] = self.request.session.get("empresa") or self.request.session.get("empr") or 1
        context["filial"] = self.request.session.get("filial") or self.request.session.get("fili") or 1

        if self.request.method == "POST":
            try:
                posted = self.request.POST.get("itens_json")
                if posted:
                    context["itens_json"] = json.loads(posted)
            except Exception:
                pass
        return context
