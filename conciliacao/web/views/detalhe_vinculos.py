import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from Entidades.models import Entidades

from conciliacao.contexto import obter_contexto
from conciliacao.models import ConciliacaoHist, ItemExtrato
from conciliacao.services.conciliar import ConciliarExtratoService

logger = logging.getLogger(__name__)


@login_required
@require_GET
def detalhe_vinculos(request, slug, empresa, filial, numero, item_id):

    ctx = obter_contexto(request, slug, acao="view")

    if empresa != ctx.empresa or filial != ctx.filial:
        return JsonResponse(
            {"erro": "Sem acesso."},
            status=403,
        )

    try:
        item = (
            ItemExtrato.objects
            .using(ctx.db_alias)
            .filter(
                id=item_id,
                nume=numero,
                empresa=ctx.empresa,
                filial=ctx.filial,
            )
            .first()
        )

        if not item:
            return JsonResponse(
                {"erro": "Item não encontrado."},
                status=404,
            )

        service = ConciliarExtratoService(
            banco=ctx.db_alias,
            empresa=ctx.empresa,
            filial=ctx.filial,
            numero=numero,
        )

        status = service._status_conciliacao(item)

        vinculos = (
            ConciliacaoHist.objects
            .using(ctx.db_alias)
            .filter(
                nume=numero,
                empresa=ctx.empresa,
                filial=ctx.filial,
                item_extrato=item.id,
            )
            .order_by("data")
        )

        nomes_entidades = {}
        resultado = []

        for v in vinculos:

            nome_entidade = "Desconhecida"

            if v.entidade:

                if v.entidade not in nomes_entidades:
                    entidade = (
                        Entidades.objects
                        .using(ctx.db_alias)
                        .filter(
                            enti_empr=ctx.empresa,
                            enti_clie=v.entidade,
                        )
                        .first()
                    )
                    nomes_entidades[v.entidade] = (
                        entidade.enti_nome if entidade else "Desconhecida"
                    )

                nome_entidade = nomes_entidades[v.entidade]

            resultado.append({
                "id": v.id,
                "origem": v.origem,
                "titulo": v.titulo,
                "entidade": nome_entidade,
                "serie": v.serie,
                "parcela": v.parcela,
                "valor": str(v.valor),
                "controle_bancario": v.controle_bancario,
                "data": (
                    v.data.strftime("%d/%m/%Y %H:%M")
                    if v.data
                    else "—"
                ),
            })

        return JsonResponse({
            "item_id": item.id,
            "valor_extrato": str(item.valor),
            "vinculos": resultado,
            "total_vinculado": str(status["total_vinculado"]),
            "saldo": str(status["saldo"]),
        })

    except Exception:

        logger.exception(
            "Erro ao carregar vínculos. slug=%s empresa=%s filial=%s "
            "numero=%s item_id=%s",
            slug, empresa, filial, numero, item_id,
        )

        return JsonResponse(
            {"erro": "Erro ao carregar os vínculos. Consulte o log do servidor."},
            status=500,
        )