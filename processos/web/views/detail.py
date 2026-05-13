from django.views.generic import DetailView

from core.utils import get_db_from_slug
from processos.models import ChecklistItem, ChecklistModelo, Processo, ProcessoTipo
from processos.services.checklist_service import ChecklistService


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
        context["checklist_modelo"] = modelo
        context["checklist_versao"] = getattr(modelo, "chmo_vers", None)
        context["itens_pendentes"] = itens_pendentes
        context["itens_pendentes_count"] = itens_pendentes.count()
        context["itens_modelo_count"] = itens_modelo.count()
        context["tipos"] = ProcessoTipo.objects.using(ctx["db_alias"]).filter(
            prot_empr=ctx["empresa"], prot_fili=ctx["filial"]
        )
        context["modelos"] = ChecklistModelo.objects.using(ctx["db_alias"]).filter(
            chmo_empr=ctx["empresa"], chmo_fili=ctx["filial"]
        )
        return context
