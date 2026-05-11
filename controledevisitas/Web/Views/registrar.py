from django.views.generic import FormView
from django.contrib import messages
import logging
from core.utils import get_licenca_db_config
from django.urls import reverse
from django.http import HttpResponseRedirect
from controledevisitas.models import Controlevisita, ItensVisita
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from controledevisitas.service.item_visita_service import ItemVisitaService
from ..forms import ItemVisitaForm, ControleVisitaForm


class RegistrarItemVisitaView(FormView):
    template_name = 'ControleDeVisitas/item_registrar.html'
    form_class = ItemVisitaForm

    def dispatch(self, request, *args, **kwargs):
        self.slug = kwargs.get('slug')
        self.ctrl_id = kwargs.get('ctrl_id')
        self.db_alias = get_licenca_db_config(request)
        self.empresa_id = request.session.get('empresa_id') or request.headers.get('X-Empresa') or 1
        self.filial_id = request.session.get('filial_id') or request.headers.get('X-Filial') or 1
        return super().dispatch(request, *args, **kwargs)

    def get_service(self):
        return ItemVisitaService(
            banco=self.db_alias,
            empresa_id=self.empresa_id,
            filial_id=self.filial_id,
        )
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['slug'] = self.slug
        ctx['ctrl_id'] = self.ctrl_id
        try:
            visita = self.get_service().buscar_visita(self.ctrl_id)
            ctx['empresa_id'] = (
                getattr(getattr(visita, "ctrl_empresa", None), "empr_codi", None)
                or self.empresa_id
                or 1
            )
            ctx['filial_id'] = getattr(visita, "ctrl_filial", None) or self.filial_id or 1
        except Exception:
            ctx['empresa_id'] = self.empresa_id or 1
            ctx['filial_id'] = self.filial_id or 1
        return ctx

    def form_valid(self, form):
        try:
            item, calculo = self.get_service().criar_item_calculado(
                ctrl_id=self.ctrl_id,
                dados=form.cleaned_data,
            )

            messages.success(
                self.request,
                f"Item criado. Total calculado: R$ {calculo['valor_total']}"
            )

            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f"Falha ao registrar item: {e}")
            return self.form_invalid(form)

    def get_success_url(self):
        return f"/web/{self.slug}/controle-de-visitas/resumo/{self.ctrl_id}/"


class EditarItemVisitaView(FormView):
    template_name = 'ControleDeVisitas/item_registrar.html'
    form_class = ItemVisitaForm

    def dispatch(self, request, *args, **kwargs):
        self.slug = kwargs.get('slug')
        self.item_id = kwargs.get('item_id')
        self.db_alias = get_licenca_db_config(request)
        self.empresa_id = request.session.get('empresa_id') or request.headers.get('X-Empresa') or 1
        self.filial_id = request.session.get('filial_id') or request.headers.get('X-Filial') or 1
        return super().dispatch(request, *args, **kwargs)

    def get_service(self):
        return ItemVisitaService(
            banco=self.db_alias,
            empresa_id=self.empresa_id,
            filial_id=self.filial_id,
        )

    def _get_item(self):
        return ItensVisita.objects.using(self.db_alias).select_related('item_visita').get(item_id=self.item_id)

    def get_initial(self):
        item = self._get_item()
        return {
            'produto_codigo': item.item_prod,
            'quantidade': item.item_m2 if item.item_m2 is not None else item.item_quan,
            'percentual_quebra': item.item_queb,
            'valor_unitario': item.item_unit,
            'observacoes': item.item_obse,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        item = self._get_item()
        ctx['slug'] = self.slug
        ctx['ctrl_id'] = getattr(getattr(item, 'item_visita', None), 'ctrl_id', None)
        ctx['editando'] = True
        ctx['item_id'] = self.item_id
        ctx['produto_pre_id'] = item.item_prod
        ctx['produto_pre_nome'] = item.item_desc_prod or item.item_prod
        ctx['empresa_id'] = getattr(getattr(getattr(item, 'item_visita', None), 'ctrl_empresa', None), 'empr_codi', None) or self.empresa_id or 1
        ctx['filial_id'] = getattr(getattr(item, 'item_visita', None), 'ctrl_filial', None) or self.filial_id or 1
        return ctx

    def form_valid(self, form):
        try:
            item = self._get_item()
            _, calculo = self.get_service().atualizar_item_calculado(
                item=item,
                dados=form.cleaned_data,
            )
            messages.success(
                self.request,
                f"Item atualizado. Total calculado: R$ {calculo['valor_total']}"
            )
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Falha ao atualizar item: {e}")
            return self.form_invalid(form)

    def get_success_url(self):
        item = self._get_item()
        ctrl_id = getattr(getattr(item, 'item_visita', None), 'ctrl_id', None)
        return f"/web/{self.slug}/controle-de-visitas/resumo/{ctrl_id}/"


class ControleVisitaCreateView(VendedorEntidadeMixin, FormView):
    template_name = 'ControleDeVisitas/visita_criar.html'
    form_class = ControleVisitaForm

    def dispatch(self, request, *args, **kwargs):
        self.slug = kwargs.get('slug')
        self.db_alias = get_licenca_db_config(request)
        self.empresa_id = request.session.get('empresa_id') or request.headers.get('X-Empresa') or 1
        self.filial_id = request.session.get('filial_id') or request.headers.get('X-Filial') or 1
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["slug"] = self.slug

        cliente_id = self.request.GET.get("cliente")
        vendedor_id = self.request.GET.get("vendedor")

        ctx["cliente_pre_id"] = ""
        ctx["cliente_pre_nome"] = ""
        ctx["vendedor_pre_id"] = ""
        ctx["vendedor_pre_nome"] = ""

        if cliente_id:
            from Entidades.models import Entidades

            try:
                empresa_id = int(self.empresa_id)
            except Exception:
                empresa_id = None

            qs = Entidades.objects.using(self.db_alias).filter(enti_clie=cliente_id)

            if empresa_id:
                qs = qs.filter(enti_empr=empresa_id)

            cliente = qs.first()

            if cliente:
                ctx["cliente_pre_id"] = cliente.enti_clie
                ctx["cliente_pre_nome"] = cliente.enti_nome

        if vendedor_id:
            from Entidades.models import Entidades

            try:
                empresa_id = int(self.empresa_id)
            except Exception:
                empresa_id = None

            try:
                qs_vend = Entidades.objects.using(self.db_alias).filter(enti_clie=vendedor_id)
                if empresa_id:
                    qs_vend = qs_vend.filter(enti_empr=empresa_id)
                vendedor = qs_vend.first()
            except Exception:
                vendedor = None

            ctx["vendedor_pre_id"] = vendedor.enti_clie if vendedor else ""
            ctx["vendedor_pre_nome"] = vendedor.enti_nome if vendedor else ""


        return ctx
    
    
    def form_valid(self, form):

        return ctx
    
    
    def form_valid(self, form):
        dados = form.cleaned_data
        from Entidades.models import Entidades
        from Licencas.models import Empresas, Filiais
        empresa_id = self.request.session.get('empresa_id', 1)
        filial_id = self.request.session.get('filial_id', 1) 
        try:
            empresa_id = int(self.empresa_id)
        except Exception:
            empresa_id = int(self.request.session.get('empresa_id', 1) or 1)
        try:
            filial_id = int(self.filial_id)
        except Exception:
            filial_id = int(self.request.session.get('filial_id', 1) or 1)
        try:
            cliente = (
                Entidades.objects.using(self.db_alias)
                .filter(enti_empr=empresa_id, enti_clie=dados['ctrl_cliente_id'])
                .first()
            )
        except Exception:
            try:
                cliente = Entidades.objects.using(self.db_alias).filter(enti_clie=dados['ctrl_cliente_id']).first()
            except Exception:
                cliente = None
        if not cliente:
            messages.error(self.request, 'Cliente inválido')
            return self.form_invalid(form)
        vendedor = None
        if dados.get('ctrl_vendedor_id'):
            try:
                vendedor = (
                    Entidades.objects.using(self.db_alias)
                    .filter(enti_empr=empresa_id, enti_clie=dados['ctrl_vendedor_id'])
                    .first()
                )
            except Exception:
                try:
                    vendedor = Entidades.objects.using(self.db_alias).filter(enti_clie=dados['ctrl_vendedor_id']).first()
                except Exception:
                    vendedor = None
        if not vendedor:
            vendedor = self.get_entidade_vendedor()
        etapa = None
        if dados.get('ctrl_etapa_id'):
            from controledevisitas.models import Etapavisita
            try:
                etapa = Etapavisita.objects.using(self.db_alias).get(etap_id=dados['ctrl_etapa_id'])
            except Exception:
                etapa = None
        # Obter objetos de empresa e filial da sessão
        try:
            empresa_obj = Empresas.objects.using(self.db_alias).get(empr_codi=empresa_id)
        except Exception:
            messages.error(self.request, 'Empresa inválida')
            return self.form_invalid(form)
        try:
            filial_obj = Filiais.objects.using(self.db_alias).get(empr_empr=empresa_id, empr_codi=filial_id)
        except Exception:
            messages.error(self.request, 'Filial inválida')
            return self.form_invalid(form)

        # Número da visita máximo por empresa+filial
        from django.db.models import Max
        max_numero = Controlevisita.objects.using(self.db_alias).filter(
            ctrl_empresa_id=empresa_id,
            ctrl_filial=filial_id,
        ).aggregate(Max('ctrl_numero')).get('ctrl_numero__max') or 0

        # ID máximo por empresa+filial (conforme solicitado) e global para garantir unicidade
        max_id_pair = Controlevisita.objects.using(self.db_alias).filter(
            ctrl_empresa_id=empresa_id,
            ctrl_filial=filial_id,
        ).aggregate(Max('ctrl_id')).get('ctrl_id__max') or 0
        max_id_global = Controlevisita.objects.using(self.db_alias).aggregate(Max('ctrl_id')).get('ctrl_id__max') or 0
        new_ctrl_id = max(max_id_pair, max_id_global) + 1
        try:
            logging.info(f"Criando visita: empresa_id={empresa_id}, filial_id={filial_id}, ctrl_id={new_ctrl_id}, ctrl_numero={int(max_numero)+1}")
            obj = Controlevisita.objects.using(self.db_alias).create(
                ctrl_id=int(new_ctrl_id),
                ctrl_empresa=empresa_obj,
                ctrl_filial=filial_id,
                ctrl_numero=int(max_numero) + 1,
                ctrl_cliente=cliente,
                ctrl_data=dados['ctrl_data'],
                ctrl_vendedor=vendedor,
                ctrl_etapa=etapa,
                ctrl_obse=dados.get('ctrl_obse') or None,
                ctrl_contato=dados.get('ctrl_contato') or None,
                ctrl_fone=dados.get('ctrl_fone') or None,
                ctrl_km_inic=dados.get('ctrl_km_inic') or None,
                ctrl_km_fina=dados.get('ctrl_km_fina') or None,
                ctrl_prox_visi=dados.get('ctrl_prox_visi') or None,
                ctrl_novo=(1 if dados.get('ctrl_novo') else 0),
                ctrl_base=(1 if dados.get('ctrl_base') else 0),
                ctrl_prop=(1 if dados.get('ctrl_prop') else 0),
                ctrl_leva=(1 if dados.get('ctrl_leva') else 0),
                ctrl_proj=dados.get('ctrl_proj') or None,
            )
            messages.success(self.request, 'Visita criada com sucesso.')
            self.created_id = obj.ctrl_id
            return HttpResponseRedirect(self.get_success_url())
        except Exception as e:
            logging.exception("Falha ao criar visita")
            messages.error(self.request, f'Falha ao criar visita: {e}')
            return self.form_invalid(form)

    def get_success_url(self):
        return f"/web/{self.slug}/controle-de-visitas/resumo/{getattr(self, 'created_id', '') or ''}/"
    
    def get_initial(self):
        initial = super().get_initial()

        cliente_id = self.request.GET.get("cliente")
        vendedor_id = self.request.GET.get("vendedor")

        origem = self.request.GET.get("origem")

        if cliente_id:
            initial["ctrl_cliente_id"] = cliente_id
        
        if vendedor_id:
            initial["ctrl_vendedor_id"] = vendedor_id

        if origem == "sem_movimento":
            initial["ctrl_novo"] = True
            initial["ctrl_base"] = True
            initial["ctrl_obse"] = "Contato aberto pela tela de clientes sem movimento."

        return initial


class ControleVisitaEditView(FormView):
    template_name = 'ControleDeVisitas/visita_editar.html'
    form_class = ControleVisitaForm

    def dispatch(self, request, *args, **kwargs):
        self.slug = kwargs.get('slug')
        self.ctrl_id = kwargs.get('ctrl_id')
        self.db_alias = get_licenca_db_config(request)
        self.empresa_id = request.session.get('empresa_id') or request.headers.get('X-Empresa') or 1
        self.filial_id = request.session.get('filial_id') or request.headers.get('X-Filial') or 1
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        return (
            Controlevisita.objects.using(self.db_alias)
            .select_related('ctrl_etapa')
            .prefetch_related('ctrl_cliente', 'ctrl_vendedor')
            .get(ctrl_id=self.ctrl_id)
        )

    def get_initial(self):
        v = self.get_object()
        return {
            'ctrl_data': v.ctrl_data,
            'ctrl_cliente_id': getattr(getattr(v,'ctrl_cliente',None),'enti_clie',None),
            'ctrl_vendedor_id': getattr(getattr(v,'ctrl_vendedor',None),'enti_clie',None),
            'ctrl_etapa_id': getattr(getattr(v,'ctrl_etapa',None),'etap_id',None),
            'ctrl_contato': getattr(v,'ctrl_contato',None),
            'ctrl_fone': getattr(v,'ctrl_fone',None),
            'ctrl_obse': getattr(v,'ctrl_obse',None),
            'ctrl_prox_visi': getattr(v,'ctrl_prox_visi',None),
            'ctrl_km_inic': getattr(v,'ctrl_km_inic',None),
            'ctrl_km_fina': getattr(v,'ctrl_km_fina',None),
            'ctrl_novo': bool(getattr(v,'ctrl_novo',0)),
            'ctrl_base': bool(getattr(v,'ctrl_base',0)),
            'ctrl_prop': bool(getattr(v,'ctrl_prop',0)),
            'ctrl_leva': bool(getattr(v,'ctrl_leva',0)),
            'ctrl_proj': getattr(v,'ctrl_proj',None),
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        v = self.get_object()
        ctx['slug'] = self.slug
        ctx['visita'] = v
        return ctx

    def form_valid(self, form):
        dados = form.cleaned_data
        v = self.get_object()
        from Entidades.models import Entidades
        vendedor = None
        cliente = None
        etapa = None
        try:
            empresa_id = int(self.empresa_id)
        except Exception:
            empresa_id = None
        if dados.get('ctrl_cliente_id'):
            if empresa_id is None:
                try:
                    cliente = Entidades.objects.using(self.db_alias).filter(enti_clie=dados['ctrl_cliente_id']).first()
                except Exception:
                    cliente = None
            else:
                try:
                    cliente = (
                        Entidades.objects.using(self.db_alias)
                        .filter(enti_empr=empresa_id, enti_clie=dados['ctrl_cliente_id'])
                        .first()
                    )
                except Exception:
                    try:
                        cliente = Entidades.objects.using(self.db_alias).filter(enti_clie=dados['ctrl_cliente_id']).first()
                    except Exception:
                        cliente = None
        if dados.get('ctrl_vendedor_id'):
            if empresa_id is None:
                try:
                    vendedor = Entidades.objects.using(self.db_alias).filter(enti_clie=dados['ctrl_vendedor_id']).first()
                except Exception:
                    vendedor = None
            else:
                try:
                    vendedor = (
                        Entidades.objects.using(self.db_alias)
                        .filter(enti_empr=empresa_id, enti_clie=dados['ctrl_vendedor_id'])
                        .first()
                    )
                except Exception:
                    try:
                        vendedor = Entidades.objects.using(self.db_alias).filter(enti_clie=dados['ctrl_vendedor_id']).first()
                    except Exception:
                        vendedor = None
        if dados.get('ctrl_etapa_id'):
            from controledevisitas.models import Etapavisita
            try:
                etapa = Etapavisita.objects.using(self.db_alias).get(etap_id=dados['ctrl_etapa_id'])
            except Exception:
                etapa = None
        try:
            v.ctrl_data = dados['ctrl_data']
            v.ctrl_cliente = cliente or v.ctrl_cliente
            v.ctrl_vendedor = vendedor or v.ctrl_vendedor
            v.ctrl_etapa = etapa or v.ctrl_etapa
            v.ctrl_contato = dados.get('ctrl_contato') or None
            v.ctrl_fone = dados.get('ctrl_fone') or None
            v.ctrl_obse = dados.get('ctrl_obse') or None
            v.ctrl_prox_visi = dados.get('ctrl_prox_visi') or None
            v.ctrl_km_inic = dados.get('ctrl_km_inic') or None
            v.ctrl_km_fina = dados.get('ctrl_km_fina') or None
            v.ctrl_novo = 1 if dados.get('ctrl_novo') else 0
            v.ctrl_base = 1 if dados.get('ctrl_base') else 0
            v.ctrl_prop = 1 if dados.get('ctrl_prop') else 0
            v.ctrl_leva = 1 if dados.get('ctrl_leva') else 0
            v.ctrl_proj = dados.get('ctrl_proj') or None
            v.save(using=self.db_alias)
            messages.success(self.request, 'Visita atualizada com sucesso.')
            return HttpResponseRedirect(self.get_success_url())
        except Exception as e:
            messages.error(self.request, f'Falha ao atualizar visita: {e}')
            return self.form_invalid(form)

    def get_success_url(self):
        return f"/web/{self.slug}/controle-de-visitas/resumo/{self.ctrl_id}/"
