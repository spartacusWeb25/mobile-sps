from django.shortcuts import get_object_or_404, render
from django.db.models import CharField
from django.db.models import Value
from django.db.models.functions import Cast, Coalesce, Lower

from core.utils import get_db_from_slug
from core.mixins.vendedor_mixin import VendedorEntidadeMixin
from Pisos.models import Itensorcapisos, Orcamentopisos, StatusPisos
from Produtos.models import Produtos
from Entidades.models import Entidades
from CFOP.services.fiscal_status_service import obter_status_fiscal_produtos


def _buscar_status_pisos(banco, empresa, filial, tipo, codigo):
    """
    Busca o status na tabela StatusPisos pelo código.
    Retorna (descricao, cor) ou (None, None) se não encontrar.
    """
    if codigo is None:
        return None, None

    try:
        codigo = int(codigo)
    except (ValueError, TypeError):
        return None, None

    qs = StatusPisos.objects.using(banco).filter(
        stat_tipo=tipo,
        stat_codigo=codigo,
        stat_ativo=True,
    )

    # Tenta com empresa/filial exatos primeiro
    status = qs.filter(stat_empr=empresa, stat_fili=filial).first()

    # Fallback: qualquer registro do mesmo tipo/código
    if not status:
        status = qs.first()

    if status:
        return status.stat_desc, status.stat_cor

    return None, None


def visualizar_orcamento_pisos(request, slug, pk):
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
        'orca_vend'
    )

    # First try without empresa/filial filters
    try:
        orcamento = get_object_or_404(qs, orca_nume=pk)
    except ValueError as e:
        if "year" in str(e).lower() or "out of range" in str(e).lower():
            from datetime import date
            from django.db import connections
            current_date = date.today()

            with connections[banco].cursor() as cursor:
                cursor.execute(
                    "UPDATE Orcamentopisos SET orca_data = %s, orca_data_prev_entr = %s WHERE orca_nume = %s",
                    [current_date, current_date, pk]
                )

            orcamento = get_object_or_404(qs, orca_nume=pk)
        raise
    except Exception:
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
            if "year" in str(e).lower() or "out of range" in str(e).lower():
                from datetime import date
                from django.db import connections
                current_date = date.today()

                with connections[banco].cursor() as cursor:
                    cursor.execute(
                        "UPDATE Orcamentopisos SET orca_data = %s, orca_data_prev_entr = %s WHERE orca_nume = %s",
                        [current_date, current_date, pk]
                    )

                orcamento = get_object_or_404(qs, orca_nume=pk)
            raise

    itens = list(
        Itensorcapisos.objects.using(banco)
        .filter(
            item_empr=orcamento.orca_empr,
            item_fili=orcamento.orca_fili,
            item_orca=pk,
        )
        .annotate(
            _amb_sort=Lower(
                Coalesce("item_nome_ambi", Cast("item_ambi", output_field=CharField()), Value(""))
            )
        )
        .order_by("_amb_sort", "item_ambi", "item_nume")
    )

    produtos = Produtos.objects.using(banco).filter(
        prod_codi__in=[i.item_prod for i in itens]
    )
    cliente_obj = Entidades.objects.using(banco).filter(
        enti_empr=orcamento.orca_empr,
        enti_clie=orcamento.orca_clie,
    ).first()
    cliente_nome = cliente_obj.enti_nome if cliente_obj else ''

    vendedor_obj = Entidades.objects.using(banco).filter(
        enti_empr=orcamento.orca_empr,
        enti_vend=orcamento.orca_vend,
    ).first()
    vendedor_nome = vendedor_obj.enti_nome if vendedor_obj else ''

    # Status do orçamento (nome + cor da tabela StatusPisos)
    status_nome, status_cor = _buscar_status_pisos(
        banco=banco,
        empresa=orcamento.orca_empr,
        filial=orcamento.orca_fili,
        tipo=StatusPisos.TIPO_ORCAMENTO,
        codigo=getattr(orcamento, 'orca_stat', None),
    )

    mapa_produtos = {
        p.prod_codi: p
        for p in produtos
    }

    status_map = {}
    try:
        status_map = obter_status_fiscal_produtos(
            banco=banco,
            empresa=int(orcamento.orca_empr),
            filial=int(orcamento.orca_fili),
            produtos_codigos=[i.item_prod for i in itens],
            cliente_id=int(orcamento.orca_clie) if str(getattr(orcamento, "orca_clie", "") or "").strip().isdigit() else None,
            tipo_entidade=getattr(cliente_obj, "enti_tipo_enti", None) if cliente_obj else None,
            uf_destino=getattr(cliente_obj, "enti_esta", None) if cliente_obj else None,
        )
    except Exception:
        status_map = {}

    for item in itens:
        produto = mapa_produtos.get(item.item_prod)

        item.produto_obj = produto
        item.item_prod_ncm = getattr(produto, 'prod_ncm', '')
        item.item_prod_nome = getattr(produto, 'prod_nome', '')
        item.item_caix = item.item_caix or 0
        st = status_map.get(str(getattr(item, "item_prod", "") or "").strip(), {}) if status_map else {}
        item.fiscal_ok = bool(st.get("ok"))
        item.fiscal_detalhe = st.get("detalhe")

    return render(
        request,
        "Pisos/orcamento_visualizar.html",
        {
            "slug": slug,
            "orcamento": orcamento,
            "itens": itens,
            "cliente_nome": cliente_nome,
            "vendedor_nome": vendedor_nome,
            "status_nome": status_nome,
            "status_cor": status_cor,
        }
    )