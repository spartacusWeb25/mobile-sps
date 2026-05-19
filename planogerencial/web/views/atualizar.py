from .contexto import PlanoGerencialContextMixin
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect
from ...services.plano_service import PlanoGerencialService



class PlanoGerencialInativarView(PlanoGerencialContextMixin, View):
    def get_service(self):
        return PlanoGerencialService(
            db_alias=self.get_db_alias(),
            empresa=self.get_empresa(),
        )
    def post(self, request, *args, **kwargs):
        service = self.get_service()

        try:
            service.excluir_logico(redu=kwargs["redu"])
            messages.success(request, "Conta gerencial inativada com sucesso.")
        except Exception as e:
            messages.error(request, str(e))

        return redirect(
            reverse_lazy(
                "planogerencial:plano_listar",
                kwargs={"slug": self.get_slug()},
            )
        )