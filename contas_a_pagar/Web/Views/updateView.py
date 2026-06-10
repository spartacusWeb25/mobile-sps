import json
from django.views.generic import UpdateView
from django.shortcuts import redirect
from django.contrib import messages
from core.utils import get_licenca_db_config
from ..mixin import DBAndSlugMixin
from ..forms import TitulosPagarForm
from ...models import Titulospagar
from ...validators import validar_datas_titulo
from django.core.exceptions import ValidationError
from .createView import _carregar_parcelas_planejadas, _display_fornecedor, _display_centro_custo


class TitulosPagarUpdateView(DBAndSlugMixin, UpdateView):
    model = Titulospagar
    form_class = TitulosPagarForm
    template_name = 'ContasAPagar/titulo_pagar_editar.html'

    def get_queryset(self):
        banco = get_licenca_db_config(self.request) or 'default'
        qs = Titulospagar.objects.using(banco).all()
        emp = self.request.session.get('empresa_id')
        fil = self.request.session.get('filial_id')
        if emp:
            qs = qs.filter(titu_empr=int(emp))
        if fil:
            qs = qs.filter(titu_fili=int(fil))
        return qs

    def form_valid(self, form):
        banco = get_licenca_db_config(self.request) or 'default'
        obj = self.get_object()
        dados = form.cleaned_data
        avisos = validar_datas_titulo(
            titu_emis=dados.get('titu_emis'),
            titu_venc=dados.get('titu_venc'),
        )
        for aviso in avisos:
            messages.warning(self.request, aviso)

        from ...services import atualizar_titulo_pagar
        atualizar_titulo_pagar(obj, banco=banco, dados=dados)
        return redirect('contas_a_pagar_web:titulos_pagar_list', slug=self.slug)

    def get_object(self, queryset=None):
        banco = get_licenca_db_config(self.request) or 'default'
        emp = self.request.session.get('empresa_id')
        fil = self.request.session.get('filial_id')
        titu = self.kwargs.get('titu_titu')
        parcela = self.kwargs.get('titu_parc')
        qs = Titulospagar.objects.using(banco).filter(titu_titu=titu)
        if emp:
            qs = qs.filter(titu_empr=int(emp))
        if fil:
            qs = qs.filter(titu_fili=int(fil))
        if parcela:
            qs = qs.filter(titu_parc=parcela)
        obj = qs.order_by('titu_parc','titu_venc').first()
        if not obj:
            from django.http import Http404
            raise Http404('Título a pagar não encontrado')
        return obj


class TitulosPagarParcelasUpdateView(DBAndSlugMixin, UpdateView):
    model = Titulospagar
    form_class = TitulosPagarForm
    template_name = 'ContasAPagar/parcelas_a_pagar.html'

    def get_queryset(self):
        banco = get_licenca_db_config(self.request) or 'default'
        qs = Titulospagar.objects.using(banco).all()
        if self.empresa_id:
            qs = qs.filter(titu_empr=int(self.empresa_id))
        if self.filial_id:
            qs = qs.filter(titu_fili=int(self.filial_id))
        return qs

    def get_object(self, queryset=None):
        banco = get_licenca_db_config(self.request) or 'default'
        qs = Titulospagar.objects.using(banco).filter(
            titu_forn=self.kwargs.get('titu_forn'),
            titu_titu=self.kwargs.get('titu_titu'),
            titu_seri=self.kwargs.get('titu_seri'),
        )
        if self.empresa_id:
            qs = qs.filter(titu_empr=int(self.empresa_id))
        if self.filial_id:
            qs = qs.filter(titu_fili=int(self.filial_id))
        obj = qs.order_by('titu_parc', 'titu_venc').first()
        if not obj:
            from django.http import Http404
            raise Http404('Grupo de parcelas não encontrado')
        return obj

    def _get_grupo(self):
        obj = self.object if hasattr(self, 'object') else self.get_object()
        banco = get_licenca_db_config(self.request) or 'default'
        return list(
            Titulospagar.objects.using(banco)
            .filter(
                titu_empr=obj.titu_empr,
                titu_fili=obj.titu_fili,
                titu_forn=obj.titu_forn,
                titu_titu=obj.titu_titu,
                titu_seri=obj.titu_seri,
            )
            .order_by('titu_parc', 'titu_venc')
        )

    def get_initial(self):
        initial = super().get_initial()
        grupo = self._get_grupo()
        if grupo:
            initial.update({
                'titu_forn': grupo[0].titu_forn,
                'titu_titu': grupo[0].titu_titu,
                'titu_seri': grupo[0].titu_seri,
                'titu_parc': len(grupo),
                'titu_emis': grupo[0].titu_emis,
                'titu_venc': grupo[0].titu_venc,
                'titu_form_reci': grupo[0].titu_form_reci,
                'titu_valo': sum((item.titu_valo or 0) for item in grupo),
                'titu_cecu': grupo[0].titu_cecu,
            })
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['bloquear_parcela'] = False
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        banco = get_licenca_db_config(self.request) or 'default'
        grupo = self._get_grupo()
        form = context.get('form')
        fornecedor_id = form.data.get('titu_forn') if form and form.is_bound else (grupo[0].titu_forn if grupo else None)
        centro_custo_id = form.data.get('titu_cecu') if form and form.is_bound else (grupo[0].titu_cecu if grupo else None)
        parcelas_existentes = [
            {
                'parcela': item.titu_parc,
                'vencimento': item.titu_venc.isoformat() if item.titu_venc else '',
                'valor': f'{item.titu_valo or 0}',
            }
            for item in grupo
        ]
        context.update({
            'empresa_id': self.empresa_id,
            'filial_id': self.filial_id,
            'modo_edicao': True,
            'fornecedor_display': _display_fornecedor(banco, self.empresa_id, fornecedor_id),
            'centro_custo_display': _display_centro_custo(banco, self.empresa_id, centro_custo_id),
            'parcelas_existentes_json': json.dumps(parcelas_existentes),
            'grupo_parcelas': grupo,
        })
        return context

    def form_valid(self, form):
        banco = get_licenca_db_config(self.request) or 'default'
        obj = self.get_object()
        dados = form.cleaned_data
        try:
            parcelas_planejadas = _carregar_parcelas_planejadas(self.request)
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
            return self.form_invalid(form)

        avisos = validar_datas_titulo(
            titu_emis=dados.get('titu_emis'),
            titu_venc=dados.get('titu_venc'),
        )
        if avisos:
            for aviso in avisos:
                form.add_error(None, f'⚠️ {aviso}')
            return self.form_invalid(form)

        from ...services import atualizar_grupo_parcelas_pagar
        try:
            atualizar_grupo_parcelas_pagar(
                obj,
                banco=banco,
                dados=dados,
                parcelas_planejadas=parcelas_planejadas,
            )
        except (ValidationError, ValueError) as exc:
            mensagens = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            form.add_error(None, '; '.join(mensagens))
            return self.form_invalid(form)

        messages.success(self.request, '✅ Parcelas atualizadas com sucesso!')
        return redirect('contas_a_pagar_web:parcelas_a_pagar_list', slug=self.slug)
