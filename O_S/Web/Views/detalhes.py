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
            from CFOP.services.fiscal_status_service import obter_status_fiscal_produtos

            cliente = (
                Entidades.objects.using(banco)
                .filter(enti_empr=empresa_id, enti_clie=os_obj.os_clie)
                .values('enti_nome', 'enti_tipo_enti', 'enti_esta')
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
            cliente = None

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

        status_map = {}
        try:
            status_map = obter_status_fiscal_produtos(
                banco=banco,
                empresa=int(os_obj.os_empr),
                filial=int(os_obj.os_fili),
                produtos_codigos=codigos,
                cliente_id=int(os_obj.os_clie) if str(getattr(os_obj, "os_clie", "") or "").strip().isdigit() else None,
                tipo_entidade=(cliente.get("enti_tipo_enti") if cliente else None),
                uf_destino=(cliente.get("enti_esta") if cliente else None),
            )
        except Exception:
            status_map = {}

        itens = []
        subtotal = Decimal('0.00')
        for p in pecas:
            codigo = getattr(p, 'peca_prod', None)
            nome = prod_map.get(getattr(p, 'peca_prod', None)) or getattr(p, 'peca_prod', None)
            st = status_map.get(str(codigo or "").strip(), {}) if status_map else {}
            itens.append({
                'item_tipo': 'Peça',
                'item_codigo': codigo,
                'item_nome': nome,
                'item_qtd': getattr(p, 'peca_quan', None),
                'item_preco': getattr(p, 'peca_unit', None),
                'item_subt': getattr(p, 'peca_tota', None),
                'fiscal_ok': bool(st.get("ok")),
                'fiscal_detalhe': st.get("detalhe"),
            })
            try:
                subtotal += (p.peca_tota or Decimal('0.00'))
            except Exception:
                pass

        for s in servicos:
            codigo = getattr(s, 'serv_prod', None)
            nome = prod_map.get(getattr(s, 'serv_prod', None)) or getattr(s, 'serv_prod', None)
            st = status_map.get(str(codigo or "").strip(), {}) if status_map else {}
            itens.append({
                'item_tipo': 'Serviço',
                'item_codigo': codigo,
                'item_nome': nome,
                'item_qtd': getattr(s, 'serv_quan', None),
                'item_preco': getattr(s, 'serv_unit', None),
                'item_subt': getattr(s, 'serv_tota', None),
                'fiscal_ok': bool(st.get("ok")),
                'fiscal_detalhe': st.get("detalhe"),
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
