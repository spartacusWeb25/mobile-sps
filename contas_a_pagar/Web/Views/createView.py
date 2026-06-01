from django.views.generic import CreateView
from django.shortcuts import redirect
from django.contrib import messages
from core.utils import get_licenca_db_config
from ..mixin import DBAndSlugMixin
from ..forms import TitulosPagarForm
from ...models import Titulospagar
from ...validators import validar_datas_titulo


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
        
        if avisos:
            for aviso in avisos:
                form.add_error(None, f'⚠️ {aviso}')
            return self.form_invalid(form)

        from ...services import criar_titulo_pagar, gera_parcelas_a_pagar
        self.object = criar_titulo_pagar(banco=banco, dados=dados)
        gera_parcelas_a_pagar(
            titulo=self.object,
            banco=banco,
        )
        messages.success(self.request, '✅ Parcelas criadas com sucesso!')
        return redirect('contas_a_pagar_web:parcelas_a_pagar_list', slug=self.slug)