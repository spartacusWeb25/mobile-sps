from .contexto import PlanoGerencialContextMixin
from ..forms import PlanoGerencialForm, PlanoGerencialMascaraForm as MascaraGerencialForm
from ...services.mascara_service import MascaraGerencialService
from ...models import PlanoGerencialMascara, PlanoGerencialConta
from django.views.generic import TemplateView



class PlanoGerencialListView(PlanoGerencialContextMixin, TemplateView):
    template_name = "planogerencial/plano_tree.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        service = self.get_service()

        contas = service.listar()

        context["contas"] = contas
        context["slug"] = self.get_slug()
        context["empresa"] = self.get_empresa()
        context["form"] = PlanoGerencialForm()

        try:
            mascara = service.get_mascara_ativa()
            context["mascara"] = mascara
            context["exemplo_mascara"] = MascaraGerencialService.gerar_exemplo(
                mascara.gere_nivel()
            )
        except Exception:
            context["mascara"] = None
            context["exemplo_mascara"] = None

        return context

class MascaraGerencialListView(PlanoGerencialContextMixin, TemplateView):
    template_name = "planogerencial/mascara_tree.html"
    context_object_name = "contas"
    paginate_by = 10
    ordering = ["gere_nivel"]
    
    def get_queryset(self):
        return PlanoGerencialMascara.objects.using(self.get_db_alias()).filter(
            gere_empr=self.get_empresa()
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["slug"] = self.get_slug()
        context["empresa"] = self.get_empresa()
        context["form"] = MascaraGerencialForm()
        return context
