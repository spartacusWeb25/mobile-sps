from django.views.generic import DetailView
from core.utils import get_licenca_db_config
from decimal import Decimal

from ...models import Os, PecasOs, ServicosOs

class OsDetailView(DetailView):
    model = Os
    template_name = 'Os/os_detalhe.html'

    def get_queryset(self):
        banco = get_licenca_db_config(self.request) or 'default'
        return Os.objects.using(banco).filter(
            os_empr=self.request.session.get('empresa_id', 1),
            os_fili=self.request.session.get('filial_id', 1),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')
        banco = get_licenca_db_config(self.request) or 'default'
        empresa_id = self.request.session.get('empresa_id', 1)
        os_obj = context.get('object')

        context['cliente_nome'] = 'N/A'
        context['vendedor_nome'] = 'N/A'
        context['itens'] = []

        if not os_obj:
            return context

        try:
            from Entidades.models import Entidades

            cliente = (
                Entidades.objects.using(banco)
                .filter(enti_empr=empresa_id, enti_clie=os_obj.os_clie)
                .values('enti_nome')
                .first()
            )
            vendedor = (
                Entidades.objects.using(banco)
                .filter(enti_empr=empresa_id, enti_clie=os_obj.os_resp)
                .values('enti_nome')
                .first()
            )
            context['cliente_nome'] = cliente.get('enti_nome') if cliente else 'N/A'
            context['vendedor_nome'] = vendedor.get('enti_nome') if vendedor else 'N/A'
        except Exception:
            pass

        pecas = list(
            PecasOs.objects.using(banco)
            .filter(
                peca_empr=os_obj.os_empr,
                peca_fili=os_obj.os_fili,
                peca_os=os_obj.os_os,
            )
            .order_by('peca_item')
        )
        servicos = list(
            ServicosOs.objects.using(banco)
            .filter(
                serv_empr=os_obj.os_empr,
                serv_fili=os_obj.os_fili,
                serv_os=os_obj.os_os,
            )
            .order_by('serv_item')
        )

        codigos = []
        for p in pecas:
            if getattr(p, 'peca_prod', None):
                codigos.append(p.peca_prod)
        for s in servicos:
            if getattr(s, 'serv_prod', None):
                codigos.append(s.serv_prod)

        prod_map = {}
        if codigos:
            try:
                from Produtos.models import Produtos

                produtos = (
                    Produtos.objects.using(banco)
                    .filter(prod_codi__in=list(set(codigos)))
                    .values('prod_codi', 'prod_nome')
                )
                prod_map = {p['prod_codi']: p['prod_nome'] for p in produtos}
            except Exception:
                prod_map = {}

        itens = []
        subtotal = Decimal('0.00')
        for p in pecas:
            nome = prod_map.get(getattr(p, 'peca_prod', None)) or getattr(p, 'peca_prod', None)
            itens.append({
                'item_tipo': 'Peça',
                'item_codigo': getattr(p, 'peca_prod', None),
                'item_nome': nome,
                'item_qtd': getattr(p, 'peca_quan', None),
                'item_preco': getattr(p, 'peca_unit', None),
                'item_subt': getattr(p, 'peca_tota', None),
            })
            try:
                subtotal += (p.peca_tota or Decimal('0.00'))
            except Exception:
                pass

        for s in servicos:
            nome = prod_map.get(getattr(s, 'serv_prod', None)) or getattr(s, 'serv_prod', None)
            itens.append({
                'item_tipo': 'Serviço',
                'item_codigo': getattr(s, 'serv_prod', None),
                'item_nome': nome,
                'item_qtd': getattr(s, 'serv_quan', None),
                'item_preco': getattr(s, 'serv_unit', None),
                'item_subt': getattr(s, 'serv_tota', None),
            })
            try:
                subtotal += (s.serv_tota or Decimal('0.00'))
            except Exception:
                pass

        context['itens'] = itens
        try:
            os_obj.os_topr = subtotal
        except Exception:
            pass
        return context
