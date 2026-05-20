from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import View

from core.mixin import DBAndSlugMixin
from nfse.services.cancelamento_service import CancelamentoNfseService
from nfse.services.context import NfseContext
from nfse.services.front_error_service import FrontErrorService


class NfseCancelarView(DBAndSlugMixin, View):
    def post(self, request, pk, *args, **kwargs):
        motivo = request.POST.get('motivo')

        context = NfseContext.from_request(request, self.slug)

        try:
            CancelamentoNfseService.cancelar(context, pk, motivo)
            messages.success(request, 'NFS-e cancelada com sucesso.')
        except Exception as exc:
            messages.error(request, FrontErrorService.to_message(exc, 'Não foi possível cancelar a NFS-e.'))

        return redirect('nfse_web:list', slug=self.slug)