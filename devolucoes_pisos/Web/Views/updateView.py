import json

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import UpdateView

from core.utils import get_db_from_slug
from devolucoes_pisos.Web.forms import DevolucaoPedidoPisoForm
from devolucoes_pisos.services.troca_devolucao_service import DevolucaoPedidoPisoService


class DevolucaoPisosUpdateView(UpdateView):
    form_class = DevolucaoPedidoPisoForm
    template_name = "DevolucoesPisos/devolucao_form.html"

    def get_object(self, queryset=None):
        slug = self.kwargs.get("slug")
        banco = get_db_from_slug(slug)
        pedido_numero = int(self.kwargs.get("pk"))
        obj = DevolucaoPedidoPisoService.obter_devolucao(banco, pedido_numero)
        if not obj:
            raise Http404("Troca/Devolução não encontrada.")
        self.banco = banco
        self.slug = slug
        return obj

    def form_valid(self, form):
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
                banco=self.banco,
                pedido_numero=self.object.devo_pedi,
                usuario=usuario,
                tipo=form.cleaned_data.get("tipo") or "DEVO",
                desconto=form.cleaned_data.get("devo_desc"),
                data_devolucao=form.cleaned_data.get("devo_data"),
                itens=itens,
            )
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        messages.success(self.request, f"Troca/Devolução do pedido #{self.object.devo_pedi} atualizada com sucesso.")
        return redirect("DevolucoesPisosWeb:devolucoes_pisos_listar", slug=self.slug)

    def get_initial(self):
        initial = super().get_initial()
        try:
            itens_qs = DevolucaoPedidoPisoService.obter_itens_devolucao(
                self.banco, int(self.object.devo_empr or 0), int(self.object.devo_fili or 0), int(self.object.devo_pedi)
            )
            for it in itens_qs:
                obse = (it.item_obse or "").strip()
                if obse.startswith(getattr(DevolucaoPedidoPisoService, "OBSE_REPO_PREFIX", "SPS_REPO:")):
                    initial["tipo"] = "TROC"
                    break
        except Exception:
            pass
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["slug"] = self.kwargs.get("slug")
        context["titulo"] = f"Editar Troca/Devolução (Pisos) #{self.object.devo_pedi}"
        context["empresa"] = self.request.session.get("empresa") or self.request.session.get("empr") or 1
        context["filial"] = self.request.session.get("filial") or self.request.session.get("fili") or 1

        itens_qs = DevolucaoPedidoPisoService.obter_itens_devolucao(
            self.banco, int(self.object.devo_empr or 0), int(self.object.devo_fili or 0), int(self.object.devo_pedi)
        )
        itens_out = []
        for it in itens_qs:
            repo = DevolucaoPedidoPisoService.extrair_reposicao_de_obse(it.item_obse)
            itens_out.append(
                {
                    "item_ambi": it.item_ambi,
                    "item_prod": it.item_prod,
                    "item_m2": float(it.item_m2 or 0),
                    "item_quan": float(it.item_quan or 0),
                    "item_unit": float(it.item_unit or 0),
                    "item_suto": float(it.item_suto or 0),
                    "item_desc": float(it.item_desc or 0),
                    "item_nome_ambi": it.item_nome_ambi,
                    "item_prod_nome": it.item_prod_nome,
                    "item_obse": it.item_obse,
                    "repo_prod": repo.get("repo_prod"),
                    "repo_desc": repo.get("repo_desc"),
                    "repo_quan": repo.get("repo_quan"),
                    "repo_unit": repo.get("repo_unit"),
                    "repo_total": repo.get("repo_total"),
                }
            )
        context["itens_existentes"] = itens_out
        return context
