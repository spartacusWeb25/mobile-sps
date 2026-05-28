# controledevisitas/WEB/views_orcamento.py

from django.views import View
from django.contrib import messages
from django.shortcuts import redirect

from core.utils import get_licenca_db_config
from controledevisitas.service.gerar_orcamento_pisos_service import (
    GerarOrcamentoPisosDaVisitaService,
)


class GerarOrcamentoPisosDaVisitaView(View):
    def post(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        ctrl_id = kwargs.get("ctrl_id")

        banco = get_licenca_db_config(request)
        empresa_id = int(request.session.get("empresa_id") or request.headers.get("X-Empresa") or 1)
        filial_id = int(request.session.get("filial_id") or request.headers.get("X-Filial") or 1)

        try:
            # Verify that the service is being used correctly and that all required parameters are passed
            service = GerarOrcamentoPisosDaVisitaService(
                banco=banco,
                empresa_id=empresa_id,
                filial_id=filial_id,
                usuario=request.user,
            )

            orcamento = service.executar(
                ctrl_id=ctrl_id,
                condicao=request.POST.get("condicao") or "0",
            )

            messages.success(
                request,
                f"Orçamento #{orcamento.orca_nume} gerado com sucesso."
            )

            return redirect(
                "PisosWeb:orcamentos_pisos_editar",
                slug=slug,
                pk=orcamento.orca_nume,
            )

        except Exception as e:
            messages.error(request, f"Falha ao gerar orçamento: {e}")
            return redirect(
                f"/web/{slug}/controle-de-visitas/resumo/{ctrl_id}/"
            )
