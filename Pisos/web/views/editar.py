import json

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin

from Entidades.models import Entidades
from Pisos.models import Pedidospisos, Itenspedidospisos, StatusPisos

from Pisos.services.cliente_service import ClienteEnderecoService
from Pisos.services.status_pisos_service import StatusPisosService
from Pisos.services.status_listar import StatusPisosServices

from Pisos.services.pedido_arquivos_service import PedidoPisosArquivosService
from Pisos.services.pedido_atualizar_service import PedidoAtualizarService

from Pisos.web.forms import (
    PedidoPisosForm,
    ItemPedidoPisosFormSet,
    PedidosPisosArquivosForm,
)


def editar_pedido_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    # Sanitize pk - ensure it's a valid integer
    try:
        pk = int(pk)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404("Pedido inválido")

    mix = VendedorEntidadeMixin()
    mix.request = request

    qs = mix.filter_por_vendedor(
        Pedidospisos.objects.using(banco),
        "pedi_vend"
    )

    empresa_id = (
        request.session.get("empresa_id")
        or request.session.get("empresa")
        or request.session.get("empr_codi")
    )
    filial_id = (
        request.session.get("filial_id")
        or request.session.get("filial")
        or request.session.get("fili_codi")
    )
    if not empresa_id or not filial_id:
        messages.error(request, "Sessão inválida: empresa/filial não informadas.")
        return redirect("PisosWeb:pedidos_pisos_listar", slug=slug)

    if empresa_id is not None:
        try:
            qs = qs.filter(pedi_empr=int(empresa_id))
        except Exception:
            qs = qs.filter(pedi_empr=empresa_id)
    if filial_id is not None:
        try:
            qs = qs.filter(pedi_fili=int(filial_id))
        except Exception:
            qs = qs.filter(pedi_fili=filial_id)

    # Buscar sempre dentro da empresa/filial logada
    try:
        pedido = get_object_or_404(qs, pedi_nume=pk)
    except ValueError as e:
        # Handle database data corruption (invalid dates)
        if "year" in str(e).lower() or "out of range" in str(e).lower():
            # Fix corrupted dates in database
            from datetime import date
            from django.db import connections
            current_date = date.today()

            with connections[banco].cursor() as cursor:
                cursor.execute(
                    "UPDATE Pedidospisos SET pedi_data = %s WHERE pedi_nume = %s",
                    [current_date, pk]
                )

            # Retry the query after fixing
            pedido = get_object_or_404(qs, pedi_nume=pk)
        raise

    status_opcoes = StatusPisosServices.listar_status(
        banco=banco,
        empresa=pedido.pedi_empr,
        filial=pedido.pedi_fili,
        tipo=StatusPisos.TIPO_PEDIDO,
    )

    status_atual = StatusPisosServices.get_status_atual(
        banco=banco,
        empresa=pedido.pedi_empr,
        filial=pedido.pedi_fili,
        tipo=StatusPisos.TIPO_PEDIDO,
        codigo=pedido.pedi_stat,
    )

    if request.method != "POST" and getattr(pedido, "pedi_clie", None):
        precisa = any(
            not getattr(pedido, campo, None)
            for campo in [
                "pedi_ende",
                "pedi_nume_ende",
                "pedi_bair",
                "pedi_cida",
                "pedi_esta",
            ]
            if hasattr(pedido, campo)
        )

        if precisa:
            ClienteEnderecoService.preencher_pedido(
                banco=banco,
                pedido=pedido
            )

            Pedidospisos.objects.using(banco).filter(
                pedi_empr=pedido.pedi_empr,
                pedi_fili=pedido.pedi_fili,
                pedi_nume=pedido.pedi_nume,
            ).update(
                pedi_ende=getattr(pedido, "pedi_ende", None),
                pedi_nume_ende=getattr(pedido, "pedi_nume_ende", None),
                pedi_bair=getattr(pedido, "pedi_bair", None),
                pedi_cida=getattr(pedido, "pedi_cida", None),
                pedi_esta=getattr(pedido, "pedi_esta", None),
                pedi_comp=getattr(pedido, "pedi_comp", None),
                pedi_comp_fone=getattr(pedido, "pedi_comp_fone", None),
            )

    cliente_label = ""
    if pedido.pedi_clie:
        ent = Entidades.objects.using(banco).filter(
            enti_empr=pedido.pedi_empr,
            enti_clie=pedido.pedi_clie,
        ).first()

        if ent:
            cliente_label = f"{ent.enti_clie} - {ent.enti_nome}"

    vendedor_label = ""
    if pedido.pedi_vend:
        vend = Entidades.objects.using(banco).filter(
            enti_empr=pedido.pedi_empr,
            enti_clie=pedido.pedi_vend,
        ).first()

        if vend:
            vendedor_label = f"{vend.enti_clie} - {vend.enti_nome}"

    initial_itens = []

    if request.method != "POST":
        for i in Itenspedidospisos.objects.using(banco).filter(
            item_empr=pedido.pedi_empr,
            item_fili=pedido.pedi_fili,
            item_pedi=pk,
        ).order_by("item_nume"):

            initial_itens.append({
                k: getattr(i, k)
                for k in [
                    "item_ambi",
                    "item_nome_ambi",
                    "item_prod",
                    "item_prod_nome",
                    "item_m2",
                    "item_quan",
                    "item_caix",
                    "item_unit",
                    "item_suto",
                    "item_desc",
                    "item_queb",
                    "item_obse",
                ]
            })

    from decimal import Decimal
    from Produtos.models import Produtos
    from Pisos.services.calculo_services import calcular_item

    for it in initial_itens:
        try:
            prod_id = it.get("item_prod")
            produto = None

            if prod_id:
                produto = Produtos.objects.using(banco).filter(
                    prod_codi=prod_id
                ).first()

            class ItemProxy:
                pass

            ip = ItemProxy()
            ip.item_m2 = it.get("item_m2") or 0
            ip.item_queb = it.get("item_queb") or 0
            ip.item_unit = it.get("item_unit") or 0

            resultado = calcular_item(ip, produto=produto)
            kg_total = (
                resultado.get("quilos_total")
                or resultado.get("kg_total")
                or 0
            )

            it["item_kg"] = (
                Decimal(str(kg_total))
                if kg_total is not None
                else Decimal(0)
            )

        except Exception:
            it["item_kg"] = Decimal(0)

    for it in initial_itens:
        for fld in ("item_m2", "item_quan", "item_kg"):
            v = it.get(fld)

            if v is None:
                continue

            try:
                it[fld] = str(v)
            except Exception:
                pass

    item_kg = initial_itens[0].get("item_kg") if initial_itens else 0
    item = initial_itens[0] if initial_itens else {}

    itens_prod_ids = list(
        Itenspedidospisos.objects.using(banco)
        .filter(item_empr=pedido.pedi_empr, item_fili=pedido.pedi_fili, item_pedi=pedido.pedi_nume)
        .values_list("item_prod", flat=True)
    )
    itens_prod_ids = [str(p).strip() for p in itens_prod_ids if p]
    itens_prod_ids_nume = []
    for p in itens_prod_ids:
        if p.isdigit():
            try:
                itens_prod_ids_nume.append(int(p))
            except Exception:
                pass
    kohler_inicial = False
    if itens_prod_ids:
        from django.db.models import Q
        filtro = Q(prod_codi__in=list(set(itens_prod_ids)))
        if itens_prod_ids_nume:
            filtro = filtro | Q(prod_codi_nume__in=list(set(itens_prod_ids_nume)))
        produtos = (
            Produtos.objects.using(banco)
            .filter(prod_empr=str(pedido.pedi_empr))
            .filter(filtro)
            .values_list("prod_codi", "prod_codi_nume", "prod_marc_id")
        )

        marca_por_prod = {}
        for codi, codi_nume, marc_id in produtos:
            marc_str = str(marc_id).strip() if marc_id is not None else None
            if codi:
                marca_por_prod[str(codi).strip()] = marc_str
            if codi_nume:
                marca_por_prod[str(codi_nume).strip()] = marc_str

        marcas = [marca_por_prod.get(p) for p in itens_prod_ids]
        marcas_conhecidas = [m for m in marcas if m is not None and str(m).strip() != ""]
        kohler_inicial = bool(marcas_conhecidas) and all(str(m).strip() == "98" for m in marcas_conhecidas)

    if request.method == "POST":
        post_data = request.POST.copy()
        post_data["pedi_empr"] = str(pedido.pedi_empr)
        post_data["pedi_fili"] = str(pedido.pedi_fili)
        form = PedidoPisosForm(post_data, instance=pedido)
    else:
        form = PedidoPisosForm(None, instance=pedido)

    formset = ItemPedidoPisosFormSet(
        request.POST or None,
        prefix="itens",
        initial=initial_itens,
    )

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        parametros = {}
        raw_parametros = (request.POST.get("parametros") or "").strip()

        if raw_parametros:
            try:
                parametros = json.loads(raw_parametros) or {}
            except Exception:
                parametros = {}

        itens = []

        for f in formset:
            if not f.cleaned_data or f.cleaned_data.get("DELETE"):
                continue

            item_form = {
                k: v
                for k, v in f.cleaned_data.items()
                if k != "DELETE"
            }

            if item_form.get("item_prod"):
                if not item_form.get("item_ambi"):
                    item_form["item_ambi"] = len(itens) + 1

                itens.append(item_form)

        try:
            dados = {
                **form.cleaned_data,
                "parametros": parametros,
            }

            PedidoAtualizarService().executar(
                banco=banco,
                pedido=pedido,
                dados=dados,
                itens=itens,
            )

            messages.success(request, f"Pedido {pk} atualizado com sucesso.")

            return redirect(
                "PisosWeb:pedidos_pisos_visualizar",
                slug=slug,
                pk=pk,
            )

        except Exception as exc:
            try:
                from Pisos.services.status_listar import StatusPisosServices as _StatusPisosServices
                mensagem_erro = _StatusPisosServices.normalizar_erro(exc)
            except Exception:
                mensagem_erro = str(exc)

            messages.error(
                request,
                f"Erro ao atualizar pedido: {mensagem_erro}"
            )

    arquivos = []

    try:
        arquivos = PedidoPisosArquivosService.listar(
            banco,
            empresa_id=pedido.pedi_empr,
            pedido_numero=pedido.pedi_nume,
        )

        arquivos_form = PedidosPisosArquivosForm(
            initial={
                "arqu_empr": pedido.pedi_empr,
                "arqu_pedi": pedido.pedi_nume,
            }
        )

    except Exception:
        arquivos = []

        arquivos_form = PedidosPisosArquivosForm(
            initial={
                "arqu_empr": pedido.pedi_empr,
                "arqu_pedi": pedido.pedi_nume,
            }
        )

    for a in arquivos:
        nome = (getattr(a, "arqu_nome_arqu", "") or "").strip()
        setattr(a, "pode_exibir", PedidoPisosArquivosService.pode_exibir(nome))
        setattr(a, "pode_baixar", PedidoPisosArquivosService.pode_baixar(nome))

    return render(
        request,
        "Pisos/form.html",
        {
            "slug": slug,
            "form": form,
            "formset": formset,
            "modo": "editar",
            "pedido": pedido,
            "cliente_label": cliente_label,
            "vendedor_label": vendedor_label,
            "arquivos": arquivos,
            "arquivos_form": arquivos_form,
            "item_kg": item_kg,
            "item": item,
            "status_opcoes": status_opcoes,
            "status_codigo_atual": pedido.pedi_stat,
            "status_atual": status_atual,
            "kohler_inicial": kohler_inicial,
        },
    )
