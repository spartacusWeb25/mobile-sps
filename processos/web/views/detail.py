from django.views.generic import DetailView
from django.views import View
from django.contrib import messages
from django.shortcuts import redirect
from django.http import JsonResponse
from processos.services.processo_service import ProcessoService
from core.utils import get_db_from_slug
from processos.models import ChecklistItem, ChecklistModelo, Processo, ProcessoTipo
from Entidades.models import Entidades
from processos.services.checklist_service import ChecklistService
from processos.web.forms import ProcessoClienteForm


class ProcessoDetailView(DetailView):
    model = Processo
    template_name = "processos/processo_detail.html"
    context_object_name = "processo"

    def _get_db_ctx(self):
        slug = self.kwargs.get("slug")
        return {
            "slug": slug,
            "db_alias": get_db_from_slug(slug) if slug else "default",
            "empresa": self.request.session.get("empresa_id", 1),
            "filial": self.request.session.get("filial_id", 1),
        }

    def get_queryset(self):
        ctx = self._get_db_ctx()
        return (
            Processo.objects.using(ctx["db_alias"])
            .filter(proc_empr=ctx["empresa"], proc_fili=ctx["filial"])
            .select_related("proc_tipo")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ctx = self._get_db_ctx()
        processo = context["processo"]

        respostas = (
            processo.respostas.using(ctx["db_alias"])
            .filter(pchr_empr=ctx["empresa"], pchr_fili=ctx["filial"])
            .select_related("pchr_item__chit_mode")
            .order_by("pchr_item__chit_orde")
        )
        cliente = None

        if processo.proc_clie:
            cliente = (
                Entidades.objects.using(ctx["db_alias"])
                .filter(
                    enti_empr=ctx["empresa"],
                    enti_clie=processo.proc_clie,
                )
                .first()
            )

        modelo = ChecklistService.obter_modelo_ativo(
            db_alias=ctx["db_alias"],
            empresa=ctx["empresa"],
            filial=ctx["filial"],
            proc_tipo=processo.proc_tipo,
        )
        itens_modelo = ChecklistItem.objects.using(ctx["db_alias"]).none()
        itens_pendentes = ChecklistItem.objects.using(ctx["db_alias"]).none()
        if modelo:
            itens_modelo = modelo.itens.using(ctx["db_alias"]).filter(
                chit_empr=ctx["empresa"],
                chit_fili=ctx["filial"],
            )
            respostas_item_ids = list(respostas.values_list("pchr_item_id", flat=True))
            itens_pendentes = itens_modelo.exclude(id__in=respostas_item_ids).order_by(
                "chit_orde"
            )

        context["slug"] = ctx["slug"]
        context["respostas"] = respostas
        context["cliente"] = cliente
        context["checklist_modelo"] = modelo
        context["checklist_versao"] = getattr(modelo, "chmo_vers", None)
        context["itens_pendentes"] = itens_pendentes
        context["itens_pendentes_count"] = itens_pendentes.count()
        context["itens_modelo_count"] = itens_modelo.count()
        context["next_url"] = self.request.get_full_path()
        context["tipos"] = ProcessoTipo.objects.using(ctx["db_alias"]).filter(
            prot_empr=ctx["empresa"], prot_fili=ctx["filial"]
        )
        context["modelos"] = ChecklistModelo.objects.using(ctx["db_alias"]).filter(
            chmo_empr=ctx["empresa"], chmo_fili=ctx["filial"]
        )
        context["cliente_form"] = ProcessoClienteForm(
            initial={
                "proc_clie": getattr(cliente, "enti_nome", None) or (str(processo.proc_clie) if processo.proc_clie else ""),
            },
            db_alias=ctx["db_alias"],
            empresa=ctx["empresa"],
        )
        processo = context["processo"]
        return context


class ProcessoAbrirOSView(View):
    def post(self, request, slug, pk):
        db_alias = get_db_from_slug(slug)

        try:
          
            ordem = ProcessoService.avancar_ordem_de_servico(
                db_alias=db_alias,
                processo_id=pk,
                empresa=request.session.get("empresa_id"),
                filial=request.session.get("filial_id"),
                usuario_id=request.session.get("usuario_id"),
            )
            messages.success(request, f"OS #{ordem.os_os} aberta com sucesso.")
            return redirect(f"/web/{slug}/os/")
        except ValueError as e:
            messages.warning(request, str(e))
        except Exception as e:
            messages.error(request, f"Falha ao abrir OS: {e}")
        return redirect("processos:detalhe", slug=slug, pk=pk)


class ProcessoAtualizarClienteView(View):
    def post(self, request, slug, pk):
        db_alias = get_db_from_slug(slug)
        empresa = request.session.get("empresa_id", 1)
        filial = request.session.get("filial_id", 1)
        form = ProcessoClienteForm(request.POST, db_alias=db_alias, empresa=empresa)
        if not form.is_valid():
            msg = "Cliente inválido."
            try:
                msg = next(iter(form.errors.values()))[0]
            except Exception:
                pass
            messages.error(request, msg)
            return redirect("processos:detalhe", slug=slug, pk=pk)
        try:
            ProcessoService.atualizar_cliente(
                db_alias=db_alias,
                processo_id=pk,
                empresa=empresa,
                filial=filial,
                cliente_id=form.cleaned_data.get("proc_clie"),
            )
            messages.success(request, "Cliente do processo atualizado.")
        except Exception as exc:
            messages.error(request, f"Falha ao atualizar cliente: {exc}")
        return redirect("processos:detalhe", slug=slug, pk=pk)


def autocomplete_entidades(request, slug):
    db_alias = get_db_from_slug(slug) if slug else "default"
    empresa = request.session.get("empresa_id", 1)
    term = (request.GET.get("term") or "").strip()
    qs = Entidades.objects.using(db_alias).filter(enti_empr=empresa)
    if term:
        if term.isdigit():
            qs = qs.filter(enti_clie=int(term))
        else:
            qs = qs.filter(enti_nome__icontains=term)
    qs = qs.order_by("enti_nome")[:20]
    results = [{"id": int(e.enti_clie), "label": f"{e.enti_clie} - {e.enti_nome}"} for e in qs]
    return JsonResponse({"results": results})
