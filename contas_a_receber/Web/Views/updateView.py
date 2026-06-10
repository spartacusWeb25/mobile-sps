import json
from django.views.generic import UpdateView
from django.shortcuts import redirect
from django.contrib import messages
from core.utils import get_licenca_db_config
from ..mixin import DBAndSlugMixin
from ..forms import TitulosReceberForm
from ...models import Titulosreceber
from ...validators import validar_datas_titulo
from django.core.exceptions import ValidationError
from .createView import _carregar_parcelas_planejadas, _display_cliente, _display_centro_custo


class TitulosReceberUpdateView(DBAndSlugMixin, UpdateView):
    model = Titulosreceber
    form_class = TitulosReceberForm
    template_name = 'ContasAReceber/titulo_receber_editar.html'

    def get_queryset(self):
        banco = get_licenca_db_config(self.request) or 'default'
        qs = Titulosreceber.objects.using(banco).all()
        emp = self.request.session.get('empresa_id')
        fil = self.request.session.get('filial_id')
        if emp:
            qs = qs.filter(titu_empr=int(emp))
        if fil:
            qs = qs.filter(titu_fili=int(fil))
        return qs

    def get_object(self, queryset=None):
        banco = get_licenca_db_config(self.request) or 'default'
        emp = self.request.session.get('empresa_id')
        fil = self.request.session.get('filial_id')
        titu = self.kwargs.get('titu_titu')
        parcela = self.kwargs.get('titu_parc')
        qs = Titulosreceber.objects.using(banco).filter(titu_titu=titu)
        if emp:
            qs = qs.filter(titu_empr=int(emp))
        if fil:
            qs = qs.filter(titu_fili=int(fil))
        if parcela:
            qs = qs.filter(titu_parc=parcela)
        obj = qs.order_by('titu_parc','titu_venc').first()
        if not obj:
            from django.http import Http404
            raise Http404('Título a receber não encontrado')
        return obj

    def form_valid(self, form):
        banco = get_licenca_db_config(self.request) or 'default'
        obj = self.get_object()
        dados = form.cleaned_data

        emp = (self.request.session.get('empresa_id')
               or self.request.headers.get('X-Empresa')
               or getattr(self, 'empresa_id', None)
               or obj.titu_empr)
        fil = (self.request.session.get('filial_id')
               or self.request.headers.get('X-Filial')
               or getattr(self, 'filial_id', None)
               or obj.titu_fili)
        if emp is not None:
            try:
                dados['titu_empr'] = int(emp)
            except Exception:
                dados['titu_empr'] = emp
        if fil is not None:
            try:
                dados['titu_fili'] = int(fil)
            except Exception:
                dados['titu_fili'] = fil

        avisos = validar_datas_titulo(
            titu_emis=dados.get('titu_emis'),
            titu_venc=dados.get('titu_venc'),
        )
        for aviso in avisos:
            messages.warning(self.request, aviso)

        from ...services import atualizar_titulo_receber
        atualizar_titulo_receber(obj, banco=banco, dados=dados)
        return redirect('contas_a_receber_web:titulos_receber_list', slug=self.slug)


class TitulosReceberParcelasUpdateView(DBAndSlugMixin, UpdateView):
    model = Titulosreceber
    form_class = TitulosReceberForm
    template_name = 'ContasAReceber/parcelas_receber_criar.html'

    def get_queryset(self):
        banco = get_licenca_db_config(self.request) or 'default'
        qs = Titulosreceber.objects.using(banco).all()
        if self.empresa_id:
            qs = qs.filter(titu_empr=int(self.empresa_id))
        if self.filial_id:
            qs = qs.filter(titu_fili=int(self.filial_id))
        return qs

    def get_object(self, queryset=None):
        banco = get_licenca_db_config(self.request) or 'default'
        qs = Titulosreceber.objects.using(banco).filter(
            titu_clie=self.kwargs.get('titu_clie'),
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
            Titulosreceber.objects.using(banco)
            .filter(
                titu_empr=obj.titu_empr,
                titu_fili=obj.titu_fili,
                titu_clie=obj.titu_clie,
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
                'titu_clie': grupo[0].titu_clie,
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
        cliente_id = form.data.get('titu_clie') if form and form.is_bound else (grupo[0].titu_clie if grupo else None)
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
            'cliente_display': _display_cliente(banco, self.empresa_id, cliente_id),
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

        from ...services import atualizar_grupo_parcelas_receber
        try:
            atualizar_grupo_parcelas_receber(
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
        return redirect('contas_a_receber_web:parcelas_a_receber_list', slug=self.slug)
