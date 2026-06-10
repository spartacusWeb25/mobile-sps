import json
from django.views.generic import CreateView
from django.shortcuts import redirect
from django.contrib import messages
from core.utils import get_licenca_db_config
from ..mixin import DBAndSlugMixin
from ..forms import TitulosReceberForm
from ...models import Titulosreceber
from ...validators import validar_datas_titulo
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from Entidades.models import Entidades
from CentrodeCustos.models import Centrodecustos


def _carregar_parcelas_planejadas(request):
    bruto = (request.POST.get('parcelas_json') or '').strip()
    if not bruto:
        return None
    try:
        data = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ValidationError('Cronograma de parcelas inválido.') from exc
    if not isinstance(data, list):
        raise ValidationError('Cronograma de parcelas inválido.')
    return data


def _display_cliente(banco, empresa_id, cliente_id):
    if not cliente_id:
        return ''
    try:
        cliente = (
            Entidades.objects.using(banco)
            .filter(enti_empr=str(empresa_id), enti_clie=int(cliente_id))
            .only('enti_clie', 'enti_nome')
            .first()
        )
    except (TypeError, ValueError):
        cliente = None
    if not cliente:
        return str(cliente_id)
    return f'{cliente.enti_clie} - {cliente.enti_nome}'


def _display_centro_custo(banco, empresa_id, centro_custo_id):
    if not centro_custo_id:
        return ''
    try:
        centro = (
            Centrodecustos.objects.using(banco)
            .filter(cecu_empr=int(empresa_id), cecu_redu=int(centro_custo_id))
            .only('cecu_redu', 'cecu_nome')
            .first()
        )
    except (TypeError, ValueError):
        centro = None
    if not centro:
        return str(centro_custo_id)
    return f'{centro.cecu_redu} - {centro.cecu_nome}'


class TitulosReceberCreateView(DBAndSlugMixin, CreateView):
    model = Titulosreceber
    form_class = TitulosReceberForm
    template_name = 'ContasAReceber/titulo_receber_criar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get('form')
        cliente_id = None
        if form:
            cliente_id = (form.data.get('titu_clie') or form.initial.get('titu_clie'))
        context['cliente_nome'] = (self.cliente_nome(cliente_id) if cliente_id else '')
        return context
    
    def cliente_nome(self, cliente_id):
        banco = get_licenca_db_config(self.request) or 'default'
        from Entidades.models import Entidades
        try:
            cli = int(cliente_id)
        except (TypeError, ValueError):
            return ''
        try:
            emp = int(self.empresa_id) if self.empresa_id is not None else None
        except (TypeError, ValueError):
            emp = self.empresa_id
        qs = Entidades.objects.using(banco)
        qs = qs.filter(enti_clie=cli)
        if emp is not None:
            qs = qs.filter(enti_empr=emp)
        row = qs.values('enti_nome').first()
        return row.get('enti_nome') if row else ''

    def form_valid(self, form):
        banco = get_licenca_db_config(self.request) or 'default'
        dados = form.cleaned_data
        empresa = (self.request.session.get('empresa_id')
               or self.request.headers.get('X-Empresa')
               or self.request.GET.get('titu_empr')
               or getattr(self, 'empresa_id', None))
        filial = (self.request.session.get('filial_id')
               or self.request.headers.get('X-Filial')
               or self.request.GET.get('titu_fili')
               or getattr(self, 'filial_id', None))
        if empresa is not None:
            try:
                dados['titu_empr'] = int(empresa)
            except Exception:
                dados['titu_empr'] = empresa
        if filial is not None:
            try:
                dados['titu_fili'] = int(filial)
            except Exception:
                dados['titu_fili'] = filial
        
        # Verificar se já existe título com as mesmas condições
        queryset = Titulosreceber.objects.using(banco).filter(
            titu_empr=dados['titu_empr'],
            titu_fili=dados['titu_fili'],
            titu_clie=dados['titu_clie'],
            titu_titu=dados['titu_titu'],
            titu_seri=dados['titu_seri'],
            titu_parc=dados['titu_parc']
        )
        
        if queryset.exists():
            form.add_error(None, '❌ Já existe um título com essas condições (mesma empresa, filial, cliente, número, série e parcela).')
            return self.form_invalid(form)
        
        avisos = validar_datas_titulo(
            titu_emis=dados.get('titu_emis'),
            titu_venc=dados.get('titu_venc'),
        )
        for aviso in avisos:
            messages.warning(self.request, aviso)

        from ...services import criar_titulo_receber, gera_parcelas_a_receber
        self.object = criar_titulo_receber(
            banco=banco,
            dados=dados,
            empresa_id=(dados.get('titu_empr') or empresa),
            filial_id=(dados.get('titu_fili') or filial)
        )
        gera_parcelas_a_receber(
            titulo=self.object,
            banco=banco,
        )
        messages.success(self.request, '✅ Título criado com sucesso!')
        return redirect('contas_a_receber_web:titulos_receber_list', slug=self.slug)


class TitulosReceberParcelasCreateView(DBAndSlugMixin, CreateView):
    model = Titulosreceber
    form_class = TitulosReceberForm
    template_name = 'ContasAReceber/parcelas_receber_criar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        banco = get_licenca_db_config(self.request) or 'default'
        cliente_id = None
        centro_custo_id = None
        form = context.get('form')
        if form is not None:
            cliente_id = form.data.get('titu_clie') or form.initial.get('titu_clie') or getattr(form.instance, 'titu_clie', None)
            centro_custo_id = form.data.get('titu_cecu') or form.initial.get('titu_cecu') or getattr(form.instance, 'titu_cecu', None)
        context.update({
            'empresa_id': self.empresa_id,
            'filial_id': self.filial_id,
            'modo_edicao': False,
            'cliente_display': _display_cliente(banco, self.empresa_id, cliente_id),
            'centro_custo_display': _display_centro_custo(banco, self.empresa_id, centro_custo_id),
            'parcelas_existentes_json': '[]',
        })
        return context
    
    def form_valid(self, form):
        banco = get_licenca_db_config(self.request) or 'default'
        dados = form.cleaned_data
        try:
            parcelas_planejadas = _carregar_parcelas_planejadas(self.request)
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)
        empresa = (self.request.session.get('empresa_id')
               or self.request.headers.get('X-Empresa')
               or self.request.GET.get('titu_empr')
               or getattr(self, 'empresa_id', None))
        filial = (self.request.session.get('filial_id')
               or self.request.headers.get('X-Filial')
               or self.request.GET.get('titu_fili')
               or getattr(self, 'filial_id', None))
        if empresa is not None:
            try:
                dados['titu_empr'] = int(empresa)
            except Exception:
                dados['titu_empr'] = empresa
        if filial is not None:
            try:
                dados['titu_fili'] = int(filial)
            except Exception:
                dados['titu_fili'] = filial
        
        # Verificar se já existe título com as mesmas condições
        queryset = Titulosreceber.objects.using(banco).filter(
            titu_empr=dados['titu_empr'],
            titu_fili=dados['titu_fili'],
            titu_clie=dados['titu_clie'],
            titu_titu=dados['titu_titu'],
            titu_seri=dados['titu_seri'],
            titu_parc=dados['titu_parc']
        )
        
        if queryset.exists():
            form.add_error(None, '❌ Já existe um título com essas condições (mesma empresa, filial, cliente, número, série e parcela).')
            return self.form_invalid(form)
        
        avisos = validar_datas_titulo(
            titu_emis=dados.get('titu_emis'),
            titu_venc=dados.get('titu_venc'),
        )
        
        if avisos:
            for aviso in avisos:
                form.add_error(None, f'⚠️ {aviso}')
            return self.form_invalid(form)

        from ...services import criar_titulo_receber, gera_parcelas_a_receber
        
        try:
            self.object = criar_titulo_receber(
                banco=banco,
                dados=dados,
                empresa_id=(dados.get('titu_empr') or empresa),
                filial_id=(dados.get('titu_fili') or filial)
            )
        except IntegrityError:
            form.add_error(None, '❌ Já existe um título com essas condições (mesma empresa, filial, cliente, número, série e parcela).')
            return self.form_invalid(form)
        
        try:
            gera_parcelas_a_receber(
                titulo=self.object,
                banco=banco,
                parcelas_planejadas=parcelas_planejadas,
            )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
            return self.form_invalid(form)
        messages.success(self.request, '✅ Parcelas criadas com sucesso!')
        return redirect('contas_a_receber_web:parcelas_a_receber_list', slug=self.slug)
