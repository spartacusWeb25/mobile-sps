# views/clientes_sem_movimento.py

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.generic import TemplateView

from core.mixins.vendedor_responsavel_entidade_mixin import VendedorResponsavelEntidadeMixin
from core.utils import get_db_from_slug
from Entidades.models import Entidades
from Licencas.models import Empresas, Filiais
from ...service.clientes_sem_movimento import ClienteSemMovimentoService


class ClientesSemMovimentoListView(VendedorResponsavelEntidadeMixin, TemplateView):
    template_name = "ControleDeVisitas/clientes_sem_movimento.html"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%d%m%Y", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _to_input_date(value):
        return value.strftime("%Y-%m-%d") if value else ""

    # ------------------------------------------------------------------
    # request
    # ------------------------------------------------------------------

    def get(self, request, *args, **kwargs):
        self.banco = get_db_from_slug(self.kwargs["slug"])
        return super().get(request, *args, **kwargs)

    # ------------------------------------------------------------------
    # contexto
    # ------------------------------------------------------------------

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        banco = self.banco

        # --- datas -------------------------------------------------------
        data_inicial = self._parse_date(request.GET.get("data_inicial"))
        data_final   = self._parse_date(request.GET.get("data_final"))

        if data_inicial is None and data_final is None:
            data_final   = timezone.localdate() if getattr(settings, "USE_TZ", False) else datetime.now().date()
            data_inicial = data_final - timedelta(days=90)

        # --- empresa/filial ----------------------------------------------
        empresa = (request.GET.get("empresa") or "").strip() or request.session.get("empresa_id")
        filial  = (request.GET.get("filial")  or "").strip() or request.session.get("filial_id")

        # --- fetch empresas and filiais lists --------------------------------
        empresas_list = []
        filiais_list = []

        try:
            empresas_list = list(Empresas.objects.using(banco).all().order_by('empr_nome'))
        except Exception:
            pass

        try:
            filiais_list = list(Filiais.objects.using(banco).all().order_by('empr_nome'))
        except Exception:
            pass

        # --- vendedor ----------------------------------------------------
        vendedor_ids          = self.get_vendedor_responsavel_ids(banco=banco, param_name="vendedor")
        vendedor_forcado_id   = ""
        vendedor_forcado_nome = ""
        somente_carteira      = False

        if self._usuario_eh_perfil_vendedores(banco=banco):
            somente_carteira = True
            if vendedor_ids and len(vendedor_ids) == 1:
                vendedor_forcado_id = str(vendedor_ids[0])
                entidade = self.get_entidade_vendedor(banco=banco)
                vendedor_forcado_nome = (getattr(entidade, "enti_nome", "") or "").strip()

        # --- executa serviço ---------------------------------------------
        service  = ClienteSemMovimentoService(banco)
        clientes = service.listar(
            empresa=empresa,
            filial=filial,
            data_inicial=data_inicial,
            data_final=data_final,
            cliente_nome=request.GET.get("cliente"),
            vendedores_ids=vendedor_ids or None,
            somente_carteira=somente_carteira,
        )

        # --- paginação manual (lista, não QuerySet) ----------------------
        paginator   = Paginator(clientes, 50)
        page_number = request.GET.get("page") or 1
        page_obj    = paginator.get_page(page_number)

        # --- nome do vendedor pro input ----------------------------------
        vendedor_nome_input = vendedor_forcado_nome
        if not vendedor_nome_input:
            vend = (request.GET.get("vendedor") or "").strip()
            if vend.isdigit():
                try:
                    emp = request.session.get("empresa_id")
                    emp = int(emp) if emp not in (None, "") else None
                except Exception:
                    emp = None
                try:
                    qs = Entidades.objects.using(banco).filter(enti_clie=int(vend))
                    if emp is not None:
                        qs = qs.filter(enti_empr=emp)
                    obj = qs.first()
                    vendedor_nome_input = (getattr(obj, "enti_nome", "") or "").strip()
                except Exception:
                    vendedor_nome_input = ""

        # --- querystring sem page (para links de paginação) -------------
        qs_sem_page = request.GET.copy()
        qs_sem_page.pop("page", None)

        # --- contexto final ----------------------------------------------
        context.update(
            slug=self.kwargs["slug"],
            filtros=request.GET,
            empresa=request.session.get("empresa_id"),
            filial=request.session.get("filial_id"),
            empresas_list=empresas_list,
            filiais_list=filiais_list,
            data_inicial=self._to_input_date(data_inicial),
            data_final=self._to_input_date(data_final),
            data_inicial_obj=data_inicial,
            data_final_obj=data_final,
            vendedor_forcado=vendedor_forcado_id,
            vendedor_forcado_nome=vendedor_forcado_nome,
            vendedor_nome_input=vendedor_nome_input,
            qs_sem_page=qs_sem_page.urlencode(),
            # paginação
            page_obj=page_obj,
            paginator=paginator,
            clientes=page_obj.object_list,   # compatível com o template existente
            is_paginated=page_obj.has_other_pages(),
        )

        return context