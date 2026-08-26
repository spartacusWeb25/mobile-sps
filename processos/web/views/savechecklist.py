from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import View

from core.utils import get_db_from_slug
from processos.models import Processo
from processos.services.checklist_service import ChecklistService
from processos.services.validacao_service import ValidacaoProcessoService
from processos.services.processo_service import ProcessoService
from processos.web.forms import ProcessoResponsavelForm

import logging
logger = logging.getLogger(__name__)

class _ChecklistBaseView(View):
    def _ctx(self):
        slug = self.kwargs.get("slug")
        return {
            "slug": slug,
            "db_alias": get_db_from_slug(slug) if slug else "default",
            "empresa": self.request.session.get("empresa_id", 1),
            "filial": self.request.session.get("filial_id", 1),
            "usuario_id": self.request.session.get("usua_codi"),
        }

class SalvarChecklistView(_ChecklistBaseView):
    def post(self, request, pk, slug=None):
        cfg = self._ctx()
        dados = {}
        for key, value in request.POST.items():
            if key.startswith("resposta_"):
                resposta_id = key.replace("resposta_", "")
                dados[resposta_id] = {
                    "resposta": value,
                    "observacao": request.POST.get(f"observacao_{resposta_id}", ""),
                }
        ChecklistService.salvar_respostas(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo_id=pk,
            dados=dados,
        )
        messages.success(request, "Processo salvo com sucesso.")
        return redirect("processos:detalhe", slug=cfg["slug"], pk=pk)

class SincronizarChecklistView(_ChecklistBaseView):
    def post(self, request, pk, slug=None):
        cfg = self._ctx()
        processo = Processo.objects.using(cfg["db_alias"]).get(
            id=pk,
            proc_empr=cfg["empresa"],
            proc_fili=cfg["filial"],
        )
        resultado = ChecklistService.sincronizar_respostas_para_processo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo=processo,
        )

        if not resultado["modelo"]:
            messages.warning(
                request, "Nenhum modelo ativo encontrado para o tipo deste processo."
            )
        elif resultado["criadas"]:
            messages.success(
                request,
                f"{resultado['criadas']} item(ns) novo(s) foram vinculados ao processo.",
            )
        else:
            messages.info(
                request,
                "Todos os itens do modelo ativo já estavam vinculados ao processo.",
            )

        return redirect("processos:detalhe", slug=cfg["slug"], pk=pk)


class ValidarProcessoView(_ChecklistBaseView):
    def post(self, request, pk, slug=None):
        cfg = self._ctx()
        dados = {}
        processo = Processo.objects.using(cfg["db_alias"]).get(
            proc_empr=cfg["empresa"],
            proc_fili=cfg["filial"],
            id=pk,
        )
        if processo.proc_stat == Processo.STATUS_APROVADO:
            messages.error(request, "Processo já foi aprovado")
            return redirect("processos:detalhe", slug=cfg["slug"], pk=pk)
        for key, value in request.POST.items():
            if key.startswith("resposta_"):
                item_id = key.replace("resposta_", "")
                dados[item_id] = {
                    "resposta": value,
                    "observacao": request.POST.get(f"observacao_{item_id}", ""),
                }
        dados["temp_resp"] = request.POST.get("temp_resp", "").lower() == "true"
        entidades = ProcessoService.listar_entidades_responsaveis(db_alias=cfg["db_alias"],empresa=cfg["empresa"])
        form = ProcessoResponsavelForm(
            request.POST,
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            entidades=entidades
        )

        if form.is_valid():
            responsavel = form.cleaned_data["responsavel"]
            assinatura_documento = form.cleaned_data["documento"]

            if not assinatura_documento:
                messages.error(
                    request,
                    "Preencha a assinatura (documento e confirmação) para validar.",
                )
                return redirect("processos:detalhe", slug=cfg["slug"], pk=pk)

            assinatura_valida = ValidacaoProcessoService.validar_assinatura(
                db_alias=cfg["db_alias"],
                empresa=cfg["empresa"],
                responsavel_id = responsavel.enti_clie,
                documento_inserido = assinatura_documento
            )

            if not assinatura_valida:
                messages.error(
                    request,
                    "Documento inválido.",
                )
                return redirect("processos:detalhe", slug=cfg["slug"], pk=pk)

            resultado = ValidacaoProcessoService.validar_processo(
                db_alias=cfg["db_alias"],
                empresa=cfg["empresa"],
                filial=cfg["filial"],
                processo_id=pk,
                usuario_id=cfg["usuario_id"],
                responsavel_id=responsavel.enti_clie,
                dados=dados
            )

            if resultado["aprovado"]:
                messages.success(
                    request,
                    f"Processo aprovado. Assinado por {responsavel.enti_nome} ({assinatura_documento}).",
                )
            else:
                for erro in resultado["erros"]:
                    messages.error(request, erro)
            return redirect("processos:detalhe", slug=cfg["slug"], pk=pk)

        return redirect("processos:detalhe", slug=cfg["slug"], pk=pk)
