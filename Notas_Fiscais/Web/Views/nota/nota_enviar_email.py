from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View

from core.utils import get_licenca_db_config

from ....models import Nota
from ...forms import EnviarNotaEmailForm
from ....services.email_nota_service import enviar_nota_por_email


class NotaEnviarEmailView(View):
    def post(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        pk = kwargs.get("pk")
        banco = get_licenca_db_config(request) or "default"
        empresa = request.session.get("empresa_id")
        filial = request.session.get("filial_id")

        form = EnviarNotaEmailForm(request.POST)
        if not form.is_valid():
            for _, errs in form.errors.items():
                for e in errs:
                    messages.error(request, str(e))
            return HttpResponseRedirect(reverse("nota_detail_web", kwargs={"slug": slug, "pk": pk}))

        nota_qs = Nota.objects.using(banco).filter(id=pk)
        if empresa is not None:
            nota_qs = nota_qs.filter(empresa=empresa)
        if filial is not None:
            nota_qs = nota_qs.filter(filial=filial)
        nota = nota_qs.first()
        if not nota:
            messages.error(request, "Nota não encontrada.")
            return HttpResponseRedirect(reverse("notas_list_web", kwargs={"slug": slug}))

        raw_emails = form.cleaned_data.get("emails") or ""
        destinatarios = [e.strip() for e in raw_emails.replace(",", ";").split(";") if e.strip()]
        assunto = form.cleaned_data.get("assunto") or ""
        mensagem = form.cleaned_data.get("mensagem") or ""
        anexar_pdf = bool(form.cleaned_data.get("anexar_pdf"))
        anexar_xml = bool(form.cleaned_data.get("anexar_xml"))

        try:
            enviar_nota_por_email(
                banco=banco,
                nota_id=nota.id,
                destinatarios=destinatarios,
                assunto=assunto,
                mensagem=mensagem,
                anexar_pdf=anexar_pdf,
                anexar_xml=anexar_xml,
            )
        except Exception as e:
            messages.error(request, str(e))
            return HttpResponseRedirect(reverse("nota_detail_web", kwargs={"slug": slug, "pk": pk}))

        messages.success(request, "E-mail enviado com sucesso.")
        return HttpResponseRedirect(reverse("nota_detail_web", kwargs={"slug": slug, "pk": pk}))

    def get(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        pk = kwargs.get("pk")
        return HttpResponseRedirect(reverse("nota_detail_web", kwargs={"slug": slug, "pk": pk}))
