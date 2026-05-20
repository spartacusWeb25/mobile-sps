from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.mixin import DBAndSlugMixin
from nfse.Web.forms import NfseForm, NfseItemFormSet
from nfse.models import Nfse, NfseItem


class NfseEditView(DBAndSlugMixin, View):
    template_name = 'nfse/form.html'

    def _get_obj(self, request, pk):
        return get_object_or_404(
            Nfse.objects.using(request.db_alias),
            nfse_id=pk,
            nfse_empr=self.empresa_id,
            nfse_fili=self.filial_id,
        )

    def get(self, request, pk, *args, **kwargs):
        nota = self._get_obj(request, pk)
        initial = {
            'municipio_codigo': nota.nfse_muni_codi,
            'rps_numero': nota.nfse_rps_nume,
            'rps_serie': nota.nfse_rps_seri,
            'prestador_documento': nota.nfse_pres_doc,
            'prestador_nome': nota.nfse_pres_nome,
            'tomador_documento': nota.nfse_tom_doc,
            'tomador_nome': nota.nfse_tom_nome,
            'servico_codigo': nota.nfse_serv_codi,
            'servico_descricao': nota.nfse_serv_desc,
            'cnae_codigo': nota.nfse_serv_cnae,
            'lc116_codigo': nota.nfse_serv_lc116,
            'valor_servico': nota.nfse_val_serv,
            'valor_deducao': nota.nfse_val_dedu,
            'valor_desconto': nota.nfse_val_desc,
            'valor_inss': nota.nfse_val_inss,
            'valor_irrf': nota.nfse_val_irrf,
            'valor_csll': nota.nfse_val_csll,
            'valor_cofins': nota.nfse_val_cofi,
            'valor_pis': nota.nfse_val_pis,
            'valor_iss': nota.nfse_val_iss,
            'valor_liquido': nota.nfse_val_liqu,
            'aliquota_iss': nota.nfse_aliq_iss,
            'iss_retido': nota.nfse_iss_ret,
        }
        form = NfseForm(initial=initial)
        itens_qs = NfseItem.objects.using(request.db_alias).filter(nfsi_nfse_id=nota.nfse_id)
        item_initial = [
            {
                'descricao': i.nfsi_desc,
                'quantidade': i.nfsi_qtde,
                'valor_unitario': i.nfsi_unit,
                'valor_total': i.nfsi_tota,
                'servico_codigo': i.nfsi_serv_codi,
                'cnae_codigo': i.nfsi_cnae,
                'lc116_codigo': i.nfsi_lc116,
            }
            for i in itens_qs
        ]
        item_formset = NfseItemFormSet(prefix='itens', initial=item_initial)
        return render(request, self.template_name, {'form': form, 'item_formset': item_formset, 'slug': self.slug, 'modo': 'editar'})

    def post(self, request, pk, *args, **kwargs):
        nota = self._get_obj(request, pk)
        form = NfseForm(request.POST)
        item_formset = NfseItemFormSet(request.POST, prefix='itens')
        if not form.is_valid() or not item_formset.is_valid():
            return render(request, self.template_name, {'form': form, 'item_formset': item_formset, 'slug': self.slug, 'modo': 'editar'})

        for k, v in form.cleaned_data.items():
            mapping = {
                'municipio_codigo': 'nfse_muni_codi', 'rps_numero': 'nfse_rps_nume', 'rps_serie': 'nfse_rps_seri',
                'prestador_documento': 'nfse_pres_doc', 'prestador_nome': 'nfse_pres_nome', 'tomador_documento': 'nfse_tom_doc',
                'tomador_nome': 'nfse_tom_nome', 'servico_codigo': 'nfse_serv_codi', 'servico_descricao': 'nfse_serv_desc',
                'cnae_codigo': 'nfse_serv_cnae', 'lc116_codigo': 'nfse_serv_lc116', 'valor_servico': 'nfse_val_serv',
                'valor_deducao': 'nfse_val_dedu', 'valor_desconto': 'nfse_val_desc', 'valor_inss': 'nfse_val_inss',
                'valor_irrf': 'nfse_val_irrf', 'valor_csll': 'nfse_val_csll', 'valor_cofins': 'nfse_val_cofi',
                'valor_pis': 'nfse_val_pis', 'valor_iss': 'nfse_val_iss', 'valor_liquido': 'nfse_val_liqu',
                'aliquota_iss': 'nfse_aliq_iss', 'iss_retido': 'nfse_iss_ret'
            }
            if k in mapping:
                setattr(nota, mapping[k], v)
        nota.save(using=request.db_alias)
        NfseItem.objects.using(request.db_alias).filter(nfsi_nfse_id=nota.nfse_id).delete()
        ordem = 1
        for item in item_formset:
            if not item.cleaned_data or item.cleaned_data.get('DELETE'):
                continue
            NfseItem.objects.using(request.db_alias).create(
                nfsi_empr=nota.nfse_empr, nfsi_fili=nota.nfse_fili, nfsi_nfse_id=nota.nfse_id,
                nfsi_orde=ordem, nfsi_desc=item.cleaned_data['descricao'], nfsi_qtde=item.cleaned_data['quantidade'],
                nfsi_unit=item.cleaned_data['valor_unitario'], nfsi_tota=item.cleaned_data['valor_total'],
                nfsi_serv_codi=item.cleaned_data.get('servico_codigo'), nfsi_cnae=item.cleaned_data.get('cnae_codigo'),
                nfsi_lc116=item.cleaned_data.get('lc116_codigo')
            )
            ordem += 1
        messages.success(request, 'NFS-e atualizada com sucesso.')
        return redirect('nfse_web:list', slug=self.slug)
