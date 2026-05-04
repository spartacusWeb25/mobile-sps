from django.views.generic import DetailView
from django.http import Http404
import logging
from core.utils import get_licenca_db_config
from ...models import PedidoVenda
from ...services.print_service import PedidoPrintService

logger = logging.getLogger(__name__)


class PedidoPrintView(DetailView):
    model = PedidoVenda
    template_name = 'Pedidos/pedido_impressao.html'

    def get_queryset(self):
        banco = get_licenca_db_config(self.request) or 'default'
        empresa_id = self.request.session.get('empresa_id', 1)
        filial_id = self.request.session.get('filial_id', 1)
        return PedidoVenda.objects.using(banco).filter(
            pedi_empr=int(empresa_id),
            pedi_fili=int(filial_id)
        )

    def get_object(self, queryset=None):
        queryset = queryset or self.get_queryset()
        try:
            pk = int(self.kwargs.get(self.pk_url_kwarg))
        except Exception:
            raise Http404("Pedido inválido")
        obj = queryset.filter(pedi_nume=pk).first()
        if not obj:
            raise Http404("Pedido não encontrado")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')

        try:
            banco = get_licenca_db_config(self.request) or 'default'
            pedido = context.get('object')

            if pedido:
                context.update(PedidoPrintService.montar_contexto(banco=banco, pedido=pedido))

        except Exception as e:
            logger.error(f"Erro ao carregar dados da impressão: {e}")
            context['error_msg'] = "Erro ao carregar dados completos."

        return context
