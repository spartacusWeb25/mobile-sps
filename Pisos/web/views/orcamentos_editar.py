import logging

from django.contrib import messages
from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404, redirect, render

from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin

from Pisos.models import Itensorcapisos, Orcamentopisos, StatusPisos
from Pisos.services.status_pisos_service import StatusPisosService
from Pisos.services.status_listar import StatusPisosServices

from Pisos.services.orcamento_atualizar_service import OrcamentoAtualizarService
from Pisos.services.orcamento_exportar_service import OrcamentoExportarPedidoService
from Pisos.web.forms import ItemOrcamentoPisosFormSet, OrcamentoPisosForm
from Produtos.models import Produtos


logger = logging.getLogger(__name__)


def editar_orcamento_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    # Sanitize pk - ensure it's a valid integer
    try:
        pk = int(pk)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404("Orçamento inválido")

    mix = VendedorEntidadeMixin()
    mix.request = request

    qs = mix.filter_por_vendedor(
        Orcamentopisos.objects.using(banco),
        "orca_vend"
    )

    # Apply session company/branch filter to avoid picking same number from other companies
    empresa_id = (
        request.session.get('empresa_id')
        or request.session.get('empresa')
        or request.session.get('empr_codi')
    )
    filial_id = (
        request.session.get('filial_id')
        or request.session.get('filial')
        or request.session.get('fili_codi')
    )
    if empresa_id is not None:
        try:
            qs = qs.filter(orca_empr=int(empresa_id))
        except Exception:
            qs = qs.filter(orca_empr=empresa_id)
    if filial_id is not None:
        try:
            qs = qs.filter(orca_fili=int(filial_id))
        except Exception:
            qs = qs.filter(orca_fili=filial_id)

    # First try with empresa/filial filters applied
    try:
        orcamento = get_object_or_404(qs, orca_nume=pk)
    except ValueError as e:
        # Handle database data corruption (invalid dates)
        if "year" in str(e).lower() or "out of range" in str(e).lower():
            # Fix corrupted dates in database
            from datetime import date
            from django.db import connections
            current_date = date.today()

            with connections[banco].cursor() as cursor:
                cursor.execute(
                    "UPDATE Orcamentopisos SET orca_data = %s, orca_data_prev_entr = %s WHERE orca_nume = %s",
                    [current_date, current_date, pk]
                )

            # Retry the query after fixing
            orcamento = get_object_or_404(qs, orca_nume=pk)
        raise
    except Exception:
        # If multiple results, try with empresa/filial filters from session
        empresa_id = (
            request.session.get('empresa_id')
            or request.session.get('empresa')
            or request.session.get('empr_codi')
        )
        filial_id = (
            request.session.get('filial_id')
            or request.session.get('filial')
            or request.session.get('fili_codi')
        )

        if empresa_id:
            qs = qs.filter(orca_empr=empresa_id)
        if filial_id:
            qs = qs.filter(orca_fili=filial_id)

        try:
            orcamento = get_object_or_404(qs, orca_nume=pk)
        except ValueError as e:
            # Handle database data corruption (invalid dates)
            if "year" in str(e).lower() or "out of range" in str(e).lower():
                # Fix corrupted dates in database
                from datetime import date
                from django.db import connections
                current_date = date.today()

                with connections[banco].cursor() as cursor:
                    cursor.execute(
                        "UPDATE Orcamentopisos SET orca_data = %s, orca_data_prev_entr = %s WHERE orca_nume = %s",
                        [current_date, current_date, pk]
                    )

                # Retry the query after fixing
                orcamento = get_object_or_404(qs, orca_nume=pk)
            raise

    status_opcoes = StatusPisosServices.listar_status(
        banco=banco,
        empresa=orcamento.orca_empr,
        filial=orcamento.orca_fili,
        tipo=StatusPisos.TIPO_ORCAMENTO,
    )

    status_atual = StatusPisosServices.get_status_atual(
        banco=banco,
        empresa=orcamento.orca_empr,
        filial=orcamento.orca_fili,
        tipo=StatusPisos.TIPO_ORCAMENTO,
        codigo=orcamento.orca_stat,
    )

    initial_itens = []

    itens_db = list(
        Itensorcapisos.objects.using(banco).filter(
            item_empr=orcamento.orca_empr,
            item_fili=orcamento.orca_fili,
            item_orca=orcamento.orca_nume,
        ).order_by("item_nume", "item_ambi")
    )

    if request.method != "POST":
        for i in itens_db:
            initial_itens.append({
                **{
                    k: getattr(i, k)
                    for k in [
                        "item_ambi",
                        "item_nome_ambi",
                        "item_prod",
                        "item_m2",
                        "item_quan",
                        "item_caix",
                        "item_unit",
                        "item_suto",
                        "item_desc",
                        "item_queb",
                        "item_obse",
                    ]
                },
                "item_prod_nome": "",
            })

    prod_ids = [str(getattr(i, "item_prod", "") or "").strip() for i in itens_db]
    prod_ids = [p for p in prod_ids if p]
    kohler_inicial = False
    if prod_ids:
        produtos = Produtos.objects.using(banco).filter(
            prod_empr=str(orcamento.orca_empr),
        ).annotate(
            prod_codi_nume_text=Cast("prod_codi_nume", output_field=CharField())
        ).filter(
            Q(prod_codi__in=list(set(prod_ids))) | Q(prod_codi_nume_text__in=list(set(prod_ids)))
        ).values_list("prod_codi", "prod_codi_nume", "prod_nome", "prod_marc_id")

        marca_por_prod = {}
        nome_por_prod = {}
        for codi, codi_nume, nome, marc_id in produtos:
            marc_str = str(marc_id).strip() if marc_id is not None else None
            codi_str = str(codi).strip() if codi else None
            label = ""
            if codi_str:
                label = f"{codi_str} - {nome}" if nome else codi_str
                marca_por_prod[codi_str] = marc_str
                nome_por_prod[codi_str] = label
            if codi_nume:
                codi_nume_str = str(codi_nume).strip()
                if codi_nume_str:
                    marca_por_prod[codi_nume_str] = marc_str
                    nome_por_prod[codi_nume_str] = label or codi_nume_str

        marcas = [marca_por_prod.get(p) for p in prod_ids]
        marcas_conhecidas = [m for m in marcas if m is not None and str(m).strip() != ""]
        kohler_inicial = bool(marcas_conhecidas) and all(str(m).strip() == "98" for m in marcas_conhecidas)

        if request.method != "POST":
            for it in initial_itens:
                pid = str(it.get("item_prod") or "").strip()
                if not it.get("item_prod_nome") and pid:
                    it["item_prod_nome"] = nome_por_prod.get(pid) or ""

    is_post = request.method == "POST"

    if is_post:
        post_data = request.POST.copy()
        post_data["orca_empr"] = str(orcamento.orca_empr)
        post_data["orca_fili"] = str(orcamento.orca_fili)

        form = OrcamentoPisosForm(post_data, instance=orcamento)
        formset = ItemOrcamentoPisosFormSet(
            request.POST,
            prefix="itens",
            initial=initial_itens
        )
    else:
        form = OrcamentoPisosForm(None, instance=orcamento)
        formset = ItemOrcamentoPisosFormSet(
            None,
            prefix="itens",
            initial=initial_itens
        )

    is_form_valid = form.is_valid() if is_post else False
    is_formset_valid = formset.is_valid() if is_post else False

    if is_post and is_form_valid and is_formset_valid:
        itens = []

        for f in formset:
            if not f.cleaned_data or f.cleaned_data.get("DELETE"):
                continue

            item = {
                k: v
                for k, v in f.cleaned_data.items()
                if k != "DELETE"
            }

            if item.get("item_prod"):
                if not item.get("item_ambi"):
                    item["item_ambi"] = len(itens) + 1

                itens.append(item)

        try:
            StatusPisosServices().executar(
                banco=banco,
                orcamento=orcamento,
                dados=form.cleaned_data,
                itens=itens,
            )

            if request.POST.get("acao") == "exportar":
                pedido_numero = OrcamentoExportarPedidoService().executar(
                    banco=banco,
                    empresa=orcamento.orca_empr,
                    filial=orcamento.orca_fili,
                    numero=orcamento.orca_nume,
                )

                messages.success(
                    request,
                    f"Orçamento {pk} exportado para pedido {pedido_numero}."
                )

                return redirect(
                    "PisosWeb:pedidos_pisos_visualizar",
                    slug=slug,
                    pk=pedido_numero
                )

            messages.success(request, f"Orçamento {pk} atualizado com sucesso.")

            return redirect(
                "PisosWeb:orcamentos_pisos_visualizar",
                slug=slug,
                pk=pk
            )

        except Exception as exc:
            logger.exception(
                "Erro ao atualizar orçamento de pisos (slug=%s, banco=%s, orca=%s).",
                slug,
                banco,
                pk,
            )

            messages.error(
                request,
                f"Erro ao atualizar orçamento: {StatusPisosServices.normalizar_erro(exc)}"
            )

    if is_post and (not is_form_valid or not is_formset_valid):
        logger.warning(
            "Validação falhou ao editar orçamento (slug=%s, banco=%s, orca=%s). form_errors=%s formset_errors=%s formset_non_form_errors=%s",
            slug,
            banco,
            pk,
            form.errors.as_json(),
            [e for e in formset.errors],
            list(formset.non_form_errors()),
        )

    return render(
        request,
        "Pisos/orcamento_form.html",
        {
            "slug": slug,
            "form": form,
            "formset": formset,
            "modo": "editar",
            "orcamento": orcamento,
            "status_opcoes": status_opcoes,
            "status_codigo_atual": orcamento.orca_stat,
            "status_atual": status_atual,
            "kohler_inicial": kohler_inicial,
        },
    )
