from django.views.generic import ListView, DeleteView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.db import transaction
from django.db.models import Q

from core.utils import get_licenca_db_config
from transportes.models import RegraICMS, RegraPISCOFINS, RegraIBSCBS
from CFOP.models import CFOP
from transportes.forms.regras import (
    RegraICMSForm,
    RegraPISCOFINSForm,
    RegraIBSCBSForm,
)


class RegraICMSListView(ListView):
    model = RegraICMS
    template_name = "transportes/regras/regra_list.html"
    context_object_name = "regras"
    ordering = ["uf_origem", "uf_destino"]

    def get_queryset(self):
        db_alias = get_licenca_db_config(self.request)
        return RegraICMS.objects.using(db_alias).all().order_by("uf_origem", "uf_destino")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        db_alias = get_licenca_db_config(self.request)
        empresa = self.request.session.get("empresa") or self.request.session.get("empr") or 1

        def norm_cfop(value):
            v = (value or "").strip()
            return v or None

        regras = list(context.get(self.context_object_name) or [])
        cfop_codes = sorted({norm_cfop(r.cfop) for r in regras if norm_cfop(r.cfop)})

        cfop_map = {}
        if cfop_codes:
            cfop_map = {
                c["cfop_codi"]: c["cfop_desc"]
                for c in CFOP.objects.using(db_alias)
                .filter(cfop_codi__in=cfop_codes)
                .values("cfop_codi", "cfop_desc")
            }

        pis_list = list(RegraPISCOFINS.objects.using(db_alias).filter(empresa=empresa))
        ibs_list = list(RegraIBSCBS.objects.using(db_alias).filter(empresa=empresa))

        def norm_uf(value):
            v = (value or "").strip()
            return v or None

        pis_by_key = {
            (norm_uf(p.uf_origem), norm_uf(p.uf_destino), norm_cfop(p.cfop), bool(p.simples_nacional)): p
            for p in pis_list
        }
        ibs_by_key = {
            (norm_uf(i.uf_origem), norm_uf(i.uf_destino), norm_cfop(i.cfop)): i
            for i in ibs_list
        }

        rows = []
        for regra in regras:
            regra_cfop = norm_cfop(regra.cfop)
            cfop_desc = cfop_map.get(regra_cfop or "")
            cfop_display = regra_cfop if regra_cfop else "Todos"
            if regra_cfop and cfop_desc:
                cfop_display = f"{regra_cfop} - {cfop_desc}"

            is_simples = bool(regra.simples_nacional)
            uf_origem = norm_uf(regra.uf_origem)
            uf_destino = norm_uf(regra.uf_destino)

            pis = (
                pis_by_key.get((uf_origem, uf_destino, regra_cfop, is_simples))
                or pis_by_key.get((None, None, regra_cfop, is_simples))
                or pis_by_key.get((uf_origem, uf_destino, None, is_simples))
                or pis_by_key.get((None, None, None, is_simples))
                or pis_by_key.get((uf_origem, uf_destino, regra_cfop, not is_simples))
                or pis_by_key.get((None, None, regra_cfop, not is_simples))
                or pis_by_key.get((uf_origem, uf_destino, None, not is_simples))
                or pis_by_key.get((None, None, None, not is_simples))
            )

            ibs = (
                ibs_by_key.get((uf_origem, uf_destino, regra_cfop))
                or ibs_by_key.get((None, None, regra_cfop))
                or ibs_by_key.get((uf_origem, uf_destino, None))
                or ibs_by_key.get((None, None, None))
            )

            resumo = {
                "UF Origem": regra.uf_origem,
                "UF Destino": regra.uf_destino,
                "CFOP": cfop_display,
                "Contribuinte ICMS": "Sim" if regra.contribuinte else "Não",
                "Simples Nacional": "Sim" if regra.simples_nacional else "Não",
                "ICMS Alíquota": f"{regra.aliquota}%",
                "ICMS CST/CSOSN": regra.csosn if regra.simples_nacional else regra.cst,
                "PIS CST": getattr(pis, "pis_cst", "-") or "-",
                "PIS Alíquota": (f"{getattr(pis, 'pis_aliquota', '')}%" if pis else "-"),
                "COFINS CST": getattr(pis, "cofins_cst", "-") or "-",
                "COFINS Alíquota": (f"{getattr(pis, 'cofins_aliquota', '')}%" if pis else "-"),
                "IBS/CBS CST": getattr(ibs, "cst", "-") or "-",
                "CBS Alíquota": (f"{getattr(ibs, 'aliquota_cbs', '')}%" if ibs else "-"),
                "IBS UF Alíquota": (f"{getattr(ibs, 'aliquota_ibs_uf', '')}%" if ibs else "-"),
                "IBS Mun. Alíquota": (f"{getattr(ibs, 'aliquota_ibs_mun', '')}%" if ibs else "-"),
            }

            completo = {
                "ICMS UF Origem": regra.uf_origem,
                "ICMS UF Destino": regra.uf_destino,
                "ICMS CFOP": cfop_display,
                "ICMS Contribuinte": bool(regra.contribuinte),
                "ICMS Simples Nacional": bool(regra.simples_nacional),
                "ICMS Diferimento": bool(regra.diferimento),
                "ICMS Isento": bool(regra.isento),
                "ICMS Alíquota": str(regra.aliquota),
                "ICMS Alíquota Destino (DIFAL)": str(regra.aliquota_destino) if regra.aliquota_destino is not None else "",
                "ICMS Redução Base": str(regra.reducao_base),
                "ICMS MVA ST": str(regra.mva_st) if regra.mva_st is not None else "",
                "ICMS Alíquota ST": str(regra.aliquota_st) if regra.aliquota_st is not None else "",
                "ICMS Redução Base ST": str(regra.reducao_base_st) if regra.reducao_base_st is not None else "",
                "ICMS CST": str(regra.cst or ""),
                "ICMS CSOSN": str(regra.csosn or ""),
                "PIS/COFINS Encontrado": bool(pis),
                "PIS/COFINS CFOP": str(getattr(pis, "cfop", "") or ""),
                "PIS/COFINS Simples Nacional": bool(getattr(pis, "simples_nacional", False)) if pis else False,
                "PIS CST": str(getattr(pis, "pis_cst", "") or ""),
                "PIS Alíquota": str(getattr(pis, "pis_aliquota", "") or ""),
                "COFINS CST": str(getattr(pis, "cofins_cst", "") or ""),
                "COFINS Alíquota": str(getattr(pis, "cofins_aliquota", "") or ""),
                "PIS/COFINS Ativo": bool(getattr(pis, "ativo", False)) if pis else False,
                "IBS/CBS Encontrado": bool(ibs),
                "IBS/CBS CFOP": str(getattr(ibs, "cfop", "") or ""),
                "IBS/CBS CST": str(getattr(ibs, "cst", "") or ""),
                "IBS/CBS Classificação Tributária": str(getattr(ibs, "cclasstrib", "") or ""),
                "CBS Alíquota": str(getattr(ibs, "aliquota_cbs", "") or ""),
                "CBS Redução": str(getattr(ibs, "reducao_cbs", "") or ""),
                "IBS UF Alíquota": str(getattr(ibs, "aliquota_ibs_uf", "") or ""),
                "IBS UF Redução": str(getattr(ibs, "reducao_ibs_uf", "") or ""),
                "IBS Município Alíquota": str(getattr(ibs, "aliquota_ibs_mun", "") or ""),
                "IBS Município Redução": str(getattr(ibs, "reducao_ibs_mun", "") or ""),
                "IBS/CBS Ativo": bool(getattr(ibs, "ativo", False)) if ibs else False,
            }

            rows.append({
                "regra": regra,
                "cfop_display": cfop_display,
                "pis": pis,
                "ibs": ibs,
                "resumo": resumo,
                "completo": completo,
            })

        context["slug"] = db_alias
        context["rows"] = rows
        return context


class RegraICMSCreateView(View):
    template_name = "transportes/regras/regra_form.html"

    def get(self, request, *args, **kwargs):
        context = self._get_context()
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        db_alias = get_licenca_db_config(request)
        empresa = request.session.get("empresa") or request.session.get("empr") or 1

        icms_form = RegraICMSForm(
            request.POST,
            request=request,
            prefix="icms",
        )

        pis_cofins_form = RegraPISCOFINSForm(
            request.POST,
            prefix="pis",
        )

        ibs_cbs_form = RegraIBSCBSForm(
            request.POST,
            prefix="ibs",
        )

        if icms_form.is_valid() and pis_cofins_form.is_valid() and ibs_cbs_form.is_valid():
            try:
                with transaction.atomic(using=db_alias):
                    icms = icms_form.save(commit=False)
                    icms.save(using=db_alias)

                    pis = pis_cofins_form.save(commit=False)
                    pis.empresa = empresa
                    pis.uf_origem = icms.uf_origem
                    pis.uf_destino = icms.uf_destino
                    pis.simples_nacional = icms.simples_nacional
                    pis.cfop = (icms.cfop or "").strip() or None
                    pis.save(using=db_alias)

                    ibs = ibs_cbs_form.save(commit=False)
                    ibs.empresa = empresa
                    ibs.uf_origem = icms.uf_origem
                    ibs.uf_destino = icms.uf_destino
                    ibs.cfop = (icms.cfop or "").strip() or None
                    ibs.save(using=db_alias)

                messages.success(request, "Regras fiscais criadas com sucesso!")
                return redirect(self.get_success_url())

            except Exception as e:
                messages.error(request, f"Erro ao salvar regras fiscais: {e}")
        else:
            messages.error(request, "Verifique os campos obrigatórios e tente novamente.")

        return render(request, self.template_name, {
            "slug": db_alias,
            "form": icms_form,
            "pis_cofins_form": pis_cofins_form,
            "ibs_cbs_form": ibs_cbs_form,
        })

    def _get_context(self):
        return {
            "slug": get_licenca_db_config(self.request),
            "form": RegraICMSForm(
                request=self.request,
                prefix="icms",
            ),
            "pis_cofins_form": RegraPISCOFINSForm(
                prefix="pis",
            ),
            "ibs_cbs_form": RegraIBSCBSForm(
                prefix="ibs",
            ),
        }

    def get_success_url(self):
        slug = get_licenca_db_config(self.request)
        return reverse_lazy("transportes:regra_list", kwargs={"slug": slug})


class RegraICMSUpdateView(View):
    template_name = "transportes/regras/regra_form.html"

    def _select_pis(self, db_alias, empresa, cfop, simples_nacional):
        cfop = (cfop or "").strip() or None
        simples_nacional = bool(simples_nacional)
        base_qs = RegraPISCOFINS.objects.using(db_alias).filter(empresa=empresa)
        uf_origem = self._select_uf_origem
        uf_destino = self._select_uf_destino

        if cfop:
            obj = base_qs.filter(
                Q(uf_origem=uf_origem) | Q(uf_origem__isnull=True) | Q(uf_origem=""),
                Q(uf_destino=uf_destino) | Q(uf_destino__isnull=True) | Q(uf_destino=""),
                cfop=cfop,
                simples_nacional=simples_nacional,
            ).first()
            if obj:
                return obj

            obj = base_qs.filter(
                Q(uf_origem=uf_origem) | Q(uf_origem__isnull=True) | Q(uf_origem=""),
                Q(uf_destino=uf_destino) | Q(uf_destino__isnull=True) | Q(uf_destino=""),
                Q(cfop__isnull=True) | Q(cfop=""),
                simples_nacional=simples_nacional,
            ).first()
            if obj:
                return obj

            obj = base_qs.filter(
                Q(uf_origem=uf_origem) | Q(uf_origem__isnull=True) | Q(uf_origem=""),
                Q(uf_destino=uf_destino) | Q(uf_destino__isnull=True) | Q(uf_destino=""),
                cfop=cfop,
            ).first()
            if obj:
                return obj

        obj = base_qs.filter(
            Q(uf_origem=uf_origem) | Q(uf_origem__isnull=True) | Q(uf_origem=""),
            Q(uf_destino=uf_destino) | Q(uf_destino__isnull=True) | Q(uf_destino=""),
            Q(cfop__isnull=True) | Q(cfop=""),
            simples_nacional=simples_nacional,
        ).first()
        if obj:
            return obj

        return base_qs.filter(
            Q(uf_origem=uf_origem) | Q(uf_origem__isnull=True) | Q(uf_origem=""),
            Q(uf_destino=uf_destino) | Q(uf_destino__isnull=True) | Q(uf_destino=""),
            Q(cfop__isnull=True) | Q(cfop=""),
        ).first()

    def _select_ibs(self, db_alias, empresa, cfop):
        cfop = (cfop or "").strip() or None
        base_qs = RegraIBSCBS.objects.using(db_alias).filter(empresa=empresa)
        uf_origem = self._select_uf_origem
        uf_destino = self._select_uf_destino

        if cfop:
            obj = base_qs.filter(
                Q(uf_origem=uf_origem) | Q(uf_origem__isnull=True) | Q(uf_origem=""),
                Q(uf_destino=uf_destino) | Q(uf_destino__isnull=True) | Q(uf_destino=""),
                cfop=cfop,
            ).first()
            if obj:
                return obj

        return base_qs.filter(
            Q(uf_origem=uf_origem) | Q(uf_origem__isnull=True) | Q(uf_origem=""),
            Q(uf_destino=uf_destino) | Q(uf_destino__isnull=True) | Q(uf_destino=""),
            Q(cfop__isnull=True) | Q(cfop=""),
        ).first()

    def get(self, request, pk, *args, **kwargs):
        db_alias = get_licenca_db_config(request)
        empresa = request.session.get("empresa") or request.session.get("empr") or 1

        icms = RegraICMS.objects.using(db_alias).get(pk=pk)

        self._select_uf_origem = icms.uf_origem
        self._select_uf_destino = icms.uf_destino
        pis = self._select_pis(db_alias, empresa, icms.cfop, icms.simples_nacional)
        ibs = self._select_ibs(db_alias, empresa, icms.cfop)

        context = {
            "slug": db_alias,
            "form": RegraICMSForm(
                instance=icms,
                request=request,
                prefix="icms",
            ),
            "pis_cofins_form": RegraPISCOFINSForm(
                instance=pis,
                prefix="pis",
            ),
            "ibs_cbs_form": RegraIBSCBSForm(
                instance=ibs,
                prefix="ibs",
            ),
            "object": icms,
        }

        return render(request, self.template_name, context)

    def post(self, request, pk, *args, **kwargs):
        db_alias = get_licenca_db_config(request)
        empresa = request.session.get("empresa") or request.session.get("empr") or 1

        icms = RegraICMS.objects.using(db_alias).get(pk=pk)

        icms_form = RegraICMSForm(
            request.POST,
            instance=icms,
            request=request,
            prefix="icms",
        )

        pis = None
        ibs = None
        if icms_form.is_valid():
            new_cfop = (icms_form.cleaned_data.get("cfop") or "").strip() or None
            new_simples = bool(icms_form.cleaned_data.get("simples_nacional"))
            self._select_uf_origem = icms_form.cleaned_data.get("uf_origem")
            self._select_uf_destino = icms_form.cleaned_data.get("uf_destino")

            pis = self._select_pis(db_alias, empresa, new_cfop, new_simples)
            ibs = self._select_ibs(db_alias, empresa, new_cfop)
        else:
            self._select_uf_origem = icms.uf_origem
            self._select_uf_destino = icms.uf_destino
            pis = self._select_pis(db_alias, empresa, icms.cfop, icms.simples_nacional)
            ibs = self._select_ibs(db_alias, empresa, icms.cfop)

        pis_cofins_form = RegraPISCOFINSForm(request.POST, instance=pis, prefix="pis")
        ibs_cbs_form = RegraIBSCBSForm(request.POST, instance=ibs, prefix="ibs")

        if icms_form.is_valid() and pis_cofins_form.is_valid() and ibs_cbs_form.is_valid():
            try:
                with transaction.atomic(using=db_alias):
                    icms_obj = icms_form.save(commit=False)
                    icms_obj.save(using=db_alias)

                    pis_obj = pis_cofins_form.save(commit=False)
                    pis_obj.empresa = empresa
                    pis_obj.uf_origem = icms_obj.uf_origem
                    pis_obj.uf_destino = icms_obj.uf_destino
                    pis_obj.simples_nacional = icms_obj.simples_nacional
                    pis_obj.cfop = (icms_obj.cfop or "").strip() or None
                    pis_obj.save(using=db_alias)

                    ibs_obj = ibs_cbs_form.save(commit=False)
                    ibs_obj.empresa = empresa
                    ibs_obj.uf_origem = icms_obj.uf_origem
                    ibs_obj.uf_destino = icms_obj.uf_destino
                    ibs_obj.cfop = (icms_obj.cfop or "").strip() or None
                    ibs_obj.save(using=db_alias)

                messages.success(request, "Regras fiscais atualizadas com sucesso!")
                return redirect(self.get_success_url())

            except Exception as e:
                messages.error(request, f"Erro ao atualizar regras fiscais: {e}")
        else:
            messages.error(request, "Verifique os campos obrigatórios e tente novamente.")

        return render(request, self.template_name, {
            "slug": db_alias,
            "form": icms_form,
            "pis_cofins_form": pis_cofins_form,
            "ibs_cbs_form": ibs_cbs_form,
            "object": icms,
        })

    def get_success_url(self):
        slug = get_licenca_db_config(self.request)
        return reverse_lazy("transportes:regra_list", kwargs={"slug": slug})


class RegraICMSDeleteView(DeleteView):
    model = RegraICMS
    template_name = "transportes/regras/regra_confirm_delete.html"

    def get_queryset(self):
        db_alias = get_licenca_db_config(self.request)
        return RegraICMS.objects.using(db_alias).all()

    def get_success_url(self):
        slug = get_licenca_db_config(self.request)
        return reverse_lazy("transportes:regra_list", kwargs={"slug": slug})

    def delete(self, request, *args, **kwargs):
        db_alias = get_licenca_db_config(self.request)
        empresa = request.session.get("empresa") or request.session.get("empr") or 1
        self.object = self.get_object()

        with transaction.atomic(using=db_alias):
            RegraPISCOFINS.objects.using(db_alias).filter(
                empresa=empresa,
                uf_origem=self.object.uf_origem,
                uf_destino=self.object.uf_destino,
                cfop=self.object.cfop,
                simples_nacional=self.object.simples_nacional,
            ).delete()

            RegraIBSCBS.objects.using(db_alias).filter(
                empresa=empresa,
                uf_origem=self.object.uf_origem,
                uf_destino=self.object.uf_destino,
                cfop=self.object.cfop,
            ).delete()

            self.object.delete(using=db_alias)

        messages.success(self.request, "Regra excluída com sucesso!")
        return HttpResponseRedirect(self.get_success_url())
