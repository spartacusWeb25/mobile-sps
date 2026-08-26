from django.views.generic import DetailView
from processos.services.processo_service import ProcessoService
from core.utils import get_db_from_slug
from processos.models import ChecklistItem, ChecklistModelo, Processo
from processos.services.checklist_service import ChecklistService
from processos.web.forms import ProcessoResponsavelForm
from django.db.models import Q

import logging
logger = logging.getLogger(__name__)

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
            .select_related("proc_mode")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ctx = self._get_db_ctx()
        processo = context["processo"]
        if processo.proc_vers:
            vers = processo.proc_vers
        else:
            vers = 0
        respostas = list(
            processo.respostas.using(ctx["db_alias"])
            .filter(pchr_empr=ctx["empresa"], pchr_fili=ctx["filial"])
            .filter(Q(pchr_vers=vers) | Q(pchr_vers__isnull=True))
            .select_related("pchr_item__chit_mode")
        )

        modelo = ChecklistService.obter_modelo_de_processo(
            db_alias=ctx["db_alias"],
            empresa=ctx["empresa"],
            filial=ctx["filial"],
            processo_id=processo.id,
        )
        itens_modelo = ChecklistItem.objects.using(ctx["db_alias"]).none()
        temp_resp = False
        if modelo:
            itens_modelo = modelo.itens.using(ctx["db_alias"]).filter(
                chit_empr=ctx["empresa"],
                chit_fili=ctx["filial"],
            )
            mapa_modelo = {
                item.id: (item.chit_obri, item.chit_desc) 
                for item in itens_modelo
            }
            mapa_respostas = {
                r.pchr_item_id: (r.pchr_obri, r.pchr_desc) 
                for r in respostas
                if r.pchr_vers is None
            }
            if not mapa_respostas:
                mapa_respostas = {
                    r.pchr_item_id: (r.pchr_obri, r.pchr_desc) 
                    for r in respostas
                    if r.pchr_vers == vers
                }
                itens_diferenca = mapa_modelo != mapa_respostas
                temp_resp = True
            else:
                itens_diferenca = mapa_modelo != mapa_respostas
            
        context["slug"] = ctx["slug"]
        context["respostas"] = respostas
        context["checklist_modelo"] = modelo
        context["itens_diferenca"] = itens_diferenca
        context["temp_resp"] = temp_resp
        context["next_url"] = self.request.get_full_path()
        context["modelos"] = ChecklistModelo.objects.using(ctx["db_alias"]).filter(
            chmo_empr=ctx["empresa"], chmo_fili=ctx["filial"]
        )
        entidades = ProcessoService.listar_entidades_responsaveis(db_alias=ctx["db_alias"],empresa=ctx["empresa"])
        
        context["assinatura_form"] = ProcessoResponsavelForm(
            db_alias=ctx["db_alias"],
            empresa=ctx["empresa"],
            entidades=entidades
        )
        if processo.proc_enti_vali != None:
            context["responsavel"] = ProcessoService.obter_nome_responsavel(
                db_alias=ctx["db_alias"],
                empresa=ctx["empresa"],
                processo=processo
            )
        return context
