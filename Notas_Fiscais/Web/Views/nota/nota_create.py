import logging

from django.views.generic import FormView
from django.urls import reverse
from datetime import date
from core.utils import get_licenca_db_config
from ....models import Nota
from ...forms import NotaForm, NotaItemFormSet, TransporteForm, NotaFaturaForm, NotaDuplicataFormSet
from ....services.nota_service import NotaService
from ....services.calculo_impostos_service import CalculoImpostosService
from ....dominio.builder import NotaBuilder
from ..base import SPSViewMixin


logger = logging.getLogger(__name__)


class NotaCreateView(SPSViewMixin, FormView):
    template_name = "notas/nota_form.html"
    form_class = NotaForm
    success_message = "Nota criada com sucesso."

    def get_success_url(self):
        slug = self.kwargs.get("slug")
        return reverse("notas_list_web", kwargs={"slug": slug})

    def get_initial(self):
        initial = super().get_initial()
        hoje = date.today()
        initial.setdefault("data_emissao", hoje)
        initial.setdefault("data_saida", hoje)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        banco = get_licenca_db_config(self.request) or "default"
        empresa = self.request.session.get("empresa_id")

        if self.request.POST:
            nota_tmp = Nota()
            context["itens_formset"] = NotaItemFormSet(
                self.request.POST,
                form_kwargs={"database": banco, "empresa_id": empresa},
            )
            context["transporte_form"] = TransporteForm(self.request.POST)
            context["fatura_form"] = NotaFaturaForm(self.request.POST)
            context["duplicatas_formset"] = NotaDuplicataFormSet(self.request.POST, instance=nota_tmp)
        else:
            nota_tmp = Nota()
            context["itens_formset"] = NotaItemFormSet(
                form_kwargs={"database": banco, "empresa_id": empresa},
            )
            context["transporte_form"] = TransporteForm()
            context["fatura_form"] = NotaFaturaForm()
            context["duplicatas_formset"] = NotaDuplicataFormSet(instance=nota_tmp)

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        banco = get_licenca_db_config(self.request) or "default"
        empresa = self.request.session.get("empresa_id")
        kwargs.update({"database": banco, "empresa_id": empresa})
        return kwargs

    def form_valid(self, form):
        context = self.get_context_data()
        itens_fs = context["itens_formset"]
        transporte_form = context["transporte_form"]
        fatura_form = context["fatura_form"]
        duplicatas_formset = context["duplicatas_formset"]

        if not itens_fs.is_valid() or not transporte_form.is_valid() or not fatura_form.is_valid() or not duplicatas_formset.is_valid():
            return self.form_invalid(form)

        # Monta os dados
        nota_data = form.cleaned_data
        itens = []
        for f in itens_fs:
            cd = getattr(f, "cleaned_data", None) or {}
            if not cd or cd.get("DELETE"):
                continue
            if not cd.get("produto"):
                continue
            itens.append(cd)
        transporte = transporte_form.cleaned_data
        fatura = fatura_form.cleaned_data if fatura_form.has_changed() else None
        duplicatas = []
        for f in duplicatas_formset:
            cd = getattr(f, "cleaned_data", None) or {}
            if not cd or cd.get("DELETE"):
                continue
            if not str(cd.get("numero") or "").strip():
                continue
            duplicatas.append(cd)

        # Chama o service
        banco = get_licenca_db_config(self.request) or "default"
        empresa = self.request.session.get("empresa_id")
        filial = self.request.session.get("filial_id")

        nota = NotaService.criar(
            data=nota_data,
            itens=itens,
            impostos_map=None,
            transporte=transporte,
            empresa=empresa,
            filial=filial,
            database=banco,
            fatura=fatura,
            duplicatas=duplicatas,
        )

        CalculoImpostosService(banco).aplicar_impostos(nota)
        if nota:
            NotaService.gravar(nota, descricao="Rascunho criado via WEB", database=banco)

            try:
                dto = NotaBuilder(nota, database=banco).build()
                dto_payload = dto.dict()
                logger.debug(
                    "NotaCreateView.form_valid: DTO base para geração de XML da nota %s (empresa=%s, filial=%s): %s",
                    nota.pk,
                    empresa,
                    filial,
                    dto_payload,
                )
            except Exception as e:
                logger.warning("NotaCreateView.form_valid: falha ao montar DTO para nota %s: %s", nota.pk, e)

        return self.form_success()
