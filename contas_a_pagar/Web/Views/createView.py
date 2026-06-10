import json
from django.views.generic import CreateView
from django.shortcuts import redirect
from django.contrib import messages
from core.utils import get_licenca_db_config
from ..mixin import DBAndSlugMixin
from ..forms import TitulosPagarForm
from ...models import Titulospagar
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


def _display_fornecedor(banco, empresa_id, fornecedor_id):
    if not fornecedor_id:
        return ''
    try:
        fornecedor = (
            Entidades.objects.using(banco)
            .filter(enti_empr=str(empresa_id), enti_clie=int(fornecedor_id))
            .only('enti_clie', 'enti_nome')
            .first()
        )
    except (TypeError, ValueError):
        fornecedor = None
    if not fornecedor:
        return str(fornecedor_id)
    return f'{fornecedor.enti_clie} - {fornecedor.enti_nome}'


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


class TitulosPagarCreateView(DBAndSlugMixin, CreateView):
    model = Titulospagar
    form_class = TitulosPagarForm
    template_name = 'ContasAPagar/titulo_pagar_criar.html'

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
        queryset = Titulospagar.objects.using(banco).filter(
            titu_empr=dados['titu_empr'],
            titu_fili=dados['titu_fili'],
            titu_forn=dados['titu_forn'],
            titu_titu=dados['titu_titu'],
            titu_seri=dados['titu_seri'],
            titu_parc=dados['titu_parc']
        )
        if dados.get('titu_emis'):
            queryset = queryset.filter(titu_emis=dados['titu_emis'])
        if dados.get('titu_venc'):
            queryset = queryset.filter(titu_venc=dados['titu_venc'])
        
        if queryset.exists():
            form.add_error(None, '❌ Já existe um título com essas condições (mesma empresa, filial, fornecedor, número, série e parcela).')
            return self.form_invalid(form)
        
        avisos = validar_datas_titulo(
            titu_emis=dados.get('titu_emis'),
            titu_venc=dados.get('titu_venc'),
        )
        for aviso in avisos:
            messages.warning(self.request, aviso)

        from ...services import criar_titulo_pagar, gera_parcelas_a_pagar
        self.object = criar_titulo_pagar(banco=banco, dados=dados)
        gera_parcelas_a_pagar(
            titulo=self.object,
            banco=banco,
        )
        messages.success(self.request, '✅ Título criado com sucesso!')
        return redirect('contas_a_pagar_web:titulos_pagar_list', slug=self.slug)


class TitulosPagarParcelasCreateView(DBAndSlugMixin, CreateView):
    model = Titulospagar
    form_class = TitulosPagarForm
    template_name = 'ContasAPagar/parcelas_a_pagar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        banco = get_licenca_db_config(self.request) or 'default'
        fornecedor_id = None
        centro_custo_id = None
        form = context.get('form')
        if form is not None:
            fornecedor_id = form.data.get('titu_forn') or form.initial.get('titu_forn') or getattr(form.instance, 'titu_forn', None)
            centro_custo_id = form.data.get('titu_cecu') or form.initial.get('titu_cecu') or getattr(form.instance, 'titu_cecu', None)

        context.update({
            'empresa_id': self.empresa_id,
            'filial_id': self.filial_id,
            'modo_edicao': False,
            'fornecedor_display': _display_fornecedor(banco, self.empresa_id, fornecedor_id),
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
        queryset = Titulospagar.objects.using(banco).filter(
            titu_empr=dados['titu_empr'],
            titu_fili=dados['titu_fili'],
            titu_forn=dados['titu_forn'],
            titu_titu=dados['titu_titu'],
            titu_seri=dados['titu_seri'],
            titu_parc=dados['titu_parc']
        )
        if dados.get('titu_emis'):
            queryset = queryset.filter(titu_emis=dados['titu_emis'])
        if dados.get('titu_venc'):
            queryset = queryset.filter(titu_venc=dados['titu_venc'])
        
        if queryset.exists():
            form.add_error(None, '❌ Já existe um título com essas condições (mesma empresa, filial, fornecedor, número, série e parcela).')
            return self.form_invalid(form)
        
        avisos = validar_datas_titulo(
            titu_emis=dados.get('titu_emis'),
            titu_venc=dados.get('titu_venc'),
        )
        
        if avisos:
            for aviso in avisos:
                form.add_error(None, f'⚠️ {aviso}')
            return self.form_invalid(form)

        from ...services import criar_titulo_pagar, gera_parcelas_a_pagar
        

        try:
            self.object = criar_titulo_pagar(banco=banco, dados=dados)
        except IntegrityError:
            form.add_error(None, '❌ Já existe um título com essas condições (mesma empresa, filial, fornecedor, número, série e parcela).')
            return self.form_invalid(form)
        
        try:
            gera_parcelas_a_pagar(
                titulo=self.object,
                banco=banco,
                parcelas_planejadas=parcelas_planejadas,
            )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
            return self.form_invalid(form)
        messages.success(self.request, '✅ Parcelas criadas com sucesso!')
        return redirect('contas_a_pagar_web:parcelas_a_pagar_list', slug=self.slug)
