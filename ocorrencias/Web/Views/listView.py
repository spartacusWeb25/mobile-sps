from django.views.generic import ListView
from ...models import OcorrenciaTransp, PerfilOcorrencia
from core.utils import get_licenca_db_config
from ..forms import OcorrenciaForm, PerfilOcorrenciaForm

class OcorrenciaListView(ListView):
    template_name = 'ocorrencias/ocorrencia_listar.html'
    context_object_name = 'ocorrencias'
    paginate_by = 50
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = OcorrenciaForm
        context['slug'] = self.kwargs.get('slug')
        return context
    def get_queryset(self):
        banco = get_licenca_db_config(self.request) or 'default'

        qs = OcorrenciaTransp.objects.using(banco).filter(
            ocor_empr=self.request.session.get('empresa_id', 1),
            ocor_fili=self.request.session.get('filial_id', 1),
        )

        codigo_param = (self.request.GET.get('codigo') or '').strip()
        descricao_param = (self.request.GET.get('descricao') or '').strip()

        if codigo_param:
            qs = qs.filter(ocor_codi__icontains=codigo_param)

        if descricao_param:
            qs = qs.filter(ocor_desc__icontains=descricao_param)

        return qs

class PerfilOcorrenciaListView(ListView):
    template_name = 'ocorrencias/perfis_listar.html'
    context_object_name = 'perfis'
    paginate_by = 50
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PerfilOcorrenciaForm
        context['slug'] = self.kwargs.get('slug')
        banco = get_licenca_db_config(self.request) or 'default'
        context['todas_ocorrencias'] = OcorrenciaTransp.objects.using(banco).filter(
            ocor_empr = self.request.session.get('empresa_id', 1),
            ocor_fili = self.request.session.get('filial_id', 1),
        )
        return context
    def get_queryset(self):
        banco = get_licenca_db_config(self.request) or 'default'

        qs = PerfilOcorrencia.objects.using(banco).filter(
            pfoc_empr=self.request.session.get('empresa_id', 1),
            pfoc_fili=self.request.session.get('filial_id', 1),
        ).prefetch_related("ocorrencias")

        descricao_param = (self.request.GET.get('descricao') or '').strip()
        inativo_param = 'inativo' in self.request.GET

        if descricao_param:
            qs = qs.filter(pfoc_desc__icontains=descricao_param)

        if not inativo_param:
            qs = qs.filter(pfoc_ativ=True)

        return qs