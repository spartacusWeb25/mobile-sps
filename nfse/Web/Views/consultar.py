from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import View

from core.mixin import DBAndSlugMixin
from nfse.services.consulta_service import ConsultaNfseService
from nfse.services.context import NfseContext
from nfse.services.front_error_service import FrontErrorService


class NfseConsultarView(DBAndSlugMixin, View):
    def post(self, request, pk, *args, **kwargs):
        context = NfseContext.from_request(request, self.slug)

        try:
            ConsultaNfseService.consultar(context, pk)
            messages.success(request, 'Consulta realizada com sucesso.')
        except Exception as exc:
            messages.error(request, FrontErrorService.to_message(exc, 'Não foi possível consultar a NFS-e.'))

        return redirect('nfse_web:list', slug=self.slug)