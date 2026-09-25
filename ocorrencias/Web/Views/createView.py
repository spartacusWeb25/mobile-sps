from ...models import OcorrenciaTransp, PerfilOcorrencia
from ..forms import OcorrenciaForm, PerfilOcorrenciaForm
from django.views.generic import CreateView, UpdateView, View
from core.utils import get_licenca_db_config
from ...services.ocorrencia_service import OcorrenciaService
import logging
from django.shortcuts import redirect
from django.contrib import messages

logger = logging.getLogger(__name__)

class OcorrenciaCreateView(CreateView):
    model = OcorrenciaTransp
    form_class = OcorrenciaForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')
        return context
    def form_valid(self, form):
        context = self.get_context_data()
        ocor_codi = form.cleaned_data.get('ocor_codi')
        ocor_desc = form.cleaned_data.get('ocor_desc')
        ocor_fina = form.cleaned_data.get('ocor_fina')
        empresa_id = self.request.session.get('empresa_id', 1)
        filial_id = self.request.session.get('filial_id', 1)
        banco = get_licenca_db_config(self.request) or 'default'

        logger.debug("[OcorrenciaCreateView] Form valid=%s", form.is_valid())
        ocorrencia = OcorrenciaService.criar_ocorrencia(
            banco = banco,
            empresa = empresa_id,
            filial = filial_id,
            codigo = ocor_codi,
            descricao = ocor_desc,
            finalizadora = ocor_fina
        )
        logger.debug(
            "[OcorrenciaCreateView] Ocorrência criada ocor_codi=%s ocor_desc=%s ocor_fina=%s",
            getattr(ocorrencia, 'ocor_codi', None), getattr(ocorrencia, 'ocor_desc', None), getattr(ocorrencia, 'ocor_fina', None)
        )
        messages.success(self.request, f"Ocorrência {ocorrencia.ocor_codi} criada com sucesso.")
        return redirect("ocorrencias:ocorrencias", slug=context["slug"])

class PerfilOcorrenciaCreateView(CreateView):
    model = PerfilOcorrencia
    form_class = PerfilOcorrenciaForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')
        return context
    def form_valid(self, form):
        context = self.get_context_data()
        pfoc_desc = form.cleaned_data.get('pfoc_desc')
        pfoc_ativ = form.cleaned_data.get('pfoc_ativ')
        empresa_id = self.request.session.get('empresa_id', 1)
        filial_id = self.request.session.get('filial_id', 1)
        banco = get_licenca_db_config(self.request) or 'default'
        ocorrencias_selecionadas = self.request.POST.getlist('ocorrencia_ids') 
        logger.debug("[PerfilOcorrenciaCreateView] Form valid=%s", form.is_valid())
        perfil = OcorrenciaService.criar_perfil(
            banco = banco,
            empresa = empresa_id,
            filial = filial_id,
            descricao = pfoc_desc,
            ativo = pfoc_ativ,
            ocorrencias= ocorrencias_selecionadas
        )
        logger.debug(
            "[PerfilOcorrenciaCreateView] Perfil criado pfoc_desc=%s pfoc_ativ=%s",
            getattr(perfil, 'pfoc_desc', None), getattr(perfil, 'pfoc_ativ', None)
        )
        messages.success(self.request, f"Perfil {perfil.pfoc_desc} criado com sucesso.")
        return redirect("ocorrencias:perfis", slug=context["slug"])

class PerfilOcorrenciaUpdateView(UpdateView):
    model = PerfilOcorrencia
    form_class = PerfilOcorrenciaForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')
        return context
    def form_valid(self, form):
        context = self.get_context_data()
        pfoc_desc = form.cleaned_data.get('pfoc_desc')
        empresa_id = self.request.session.get('empresa_id', 1)
        filial_id = self.request.session.get('filial_id', 1)
        banco = get_licenca_db_config(self.request) or 'default'
        ocorrencias_selecionadas = self.request.POST.getlist('ocorrencia_ids') 
        logger.debug("[PerfilOcorrenciaCreateView] Form valid=%s", form.is_valid())
        perfil = OcorrenciaService.atualizar_perfil(
            banco = banco,
            empresa = empresa_id,
            filial = filial_id,
            id = self.object.id,
            descricao = pfoc_desc,
            ocorrencias= ocorrencias_selecionadas
        )
        logger.debug(
            "[PerfilOcorrenciaUpdateView] Perfil criado pfoc_desc=%s pfoc_ativ=%s",
            getattr(perfil, 'pfoc_desc', None), getattr(perfil, 'pfoc_ativ', None)
        )
        messages.success(self.request, f"Perfil {perfil.pfoc_desc} atualizado com sucesso.")
        return redirect("ocorrencias:perfis", slug=context["slug"])

class PerfilOcorrenciaToggleView(View):
    def post(self, request, *args, **kwargs):
        perfil_id = self.kwargs.get('pk')
        slug = self.kwargs.get('slug')
        empresa_id = request.session.get('empresa_id', 1)
        filial_id = request.session.get('filial_id', 1)
        banco = get_licenca_db_config(self.request) or 'default'
        perfil = OcorrenciaService.perfil_toggle_ativar(
            banco = banco,
            empresa = empresa_id,
            filial = filial_id,
            id = perfil_id
        )
        logger.debug(
            "[PerfilOcorrenciaToggleView] Status do perfil atualizado pfoc_ativ=%s",
            getattr(perfil, 'pfoc_ativ', None)
        )
        messages.success(self.request, f"Status do perfil {perfil.pfoc_desc} atualizado com sucesso.")
        return redirect("ocorrencias:perfis", slug=slug)