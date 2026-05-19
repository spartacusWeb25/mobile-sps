from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from Produtos.models import Produtos, UnidadeMedida
from Produtos.services.cadastrar_servicos import ServicoService
from ..forms import ServicosForm
from .web_views import DBAndSlugMixin


class ServicosListView(DBAndSlugMixin, ListView):
    model = Produtos
    template_name = 'Produtos/servicos_lista.html'
    context_object_name = 'servicos'
    paginate_by = 25
    
    def get_queryset(self):
        qs = Produtos.objects.using(self.db_alias).filter(prod_e_serv=True)
        if self.empresa_id:
            qs = qs.filter(prod_empr=str(self.empresa_id))
        nome = (self.request.GET.get('nome') or '').strip()
        codigo = (self.request.GET.get('codigo') or '').strip()
        if nome:
            qs = qs.filter(prod_desc_serv__icontains=nome)
        if codigo:
            qs = qs.filter(prod_codi__icontains=codigo)
        return qs.order_by('prod_codi')

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.slug
        context['nome'] = (self.request.GET.get('nome') or '').strip()
        context['codigo'] = (self.request.GET.get('codigo') or '').strip()
        return context

class ServicosCreateView(DBAndSlugMixin, CreateView):
    model = Produtos
    template_name = 'Produtos/servicos_form.html'
    form_class = ServicosForm
    
    
    def get_success_url(self):
        return reverse_lazy('servicos_web', kwargs={'slug': self.slug})

    def get_form_kwargs(self, **kwargs):
        kwargs = super().get_form_kwargs(**kwargs)
        kwargs['database'] = self.db_alias
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.slug
        return context

    def form_valid(self, form):
        unidade = form.cleaned_data.get('prod_unme')
        ServicoService.cadastrar_servico_padrao(
            banco=self.db_alias,
            empresa_id=self.empresa_id or 1,
            prod_desc=form.cleaned_data.get('prod_desc_serv') or '',
            prod_unme=unidade or '',
            prod_exig_iss=form.cleaned_data.get('prod_exig_iss') or '',
            prod_iss=form.cleaned_data.get('prod_iss') or '',
            prod_codi_serv=form.cleaned_data.get('prod_codi_serv') or '',
            prod_desc_serv=form.cleaned_data.get('prod_desc_serv') or '',
            prod_list_tabe_prec=form.cleaned_data.get('prod_list_tabe_prec'),
            prod_cnae=form.cleaned_data.get('prod_cnae') or '',
        )
        messages.success(self.request, 'Serviço cadastrado com sucesso.')
        return redirect(self.get_success_url())


class ServicosUpdateView(DBAndSlugMixin, UpdateView):
    model = Produtos
    template_name = 'Produtos/servicos_form.html'
    form_class = ServicosForm
    pk_url_kwarg = 'prod_codi'
    
    def get_success_url(self):
        return reverse_lazy('servicos_web', kwargs={'slug': self.slug})
    
    def get_queryset(self):
        qs = Produtos.objects.using(self.db_alias).filter(prod_e_serv=True)
        if self.empresa_id:
            qs = qs.filter(prod_empr=str(self.empresa_id))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.slug
        return context

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.prod_e_serv = True
        unidade = form.cleaned_data.get('prod_unme')
        if isinstance(unidade, UnidadeMedida):
            obj.prod_unme = unidade
        if self.empresa_id:
            obj.prod_empr = str(self.empresa_id)
        obj.save(using=self.db_alias)
        messages.success(self.request, 'Serviço atualizado com sucesso.')
        return redirect(self.get_success_url())


class ServicosDeleteView(DBAndSlugMixin, DeleteView):
    model = Produtos
    pk_url_kwarg = 'prod_codi'

    def get_success_url(self):
        return reverse_lazy('servicos_web', kwargs={'slug': self.slug})

    def get_queryset(self):
        qs = Produtos.objects.using(self.db_alias).filter(prod_e_serv=True)
        if self.empresa_id:
            qs = qs.filter(prod_empr=str(self.empresa_id))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.slug
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete(using=self.db_alias)
        messages.success(self.request, 'Serviço excluído com sucesso.')
        return redirect(self.get_success_url())
