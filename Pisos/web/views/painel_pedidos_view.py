# views/painel_pedidos_view.py

from django.shortcuts import render

from core.utils import get_db_from_slug
from Pisos.services.painel_gestao_compras_pisos import PainelPedidosService


def modal_painel_pedidos(request, slug):

    banco = get_db_from_slug(slug)

    empresa = request.session.get('empresa')
    filial = request.session.get('filial')

    # Fallback: aceitar empresa/filial via GET params caso a sessão esteja vazia
    req_empresa = request.GET.get('empresa') or empresa
    req_filial = request.GET.get('filial') or filial

    dados = PainelPedidosService.painel_pedidos(
        banco=banco,
        empr=req_empresa,
        fili=req_filial,
    )

    context = {
        'pedidos_pendentes': dados['pedidos_pendentes'],
        'pedidos_atrasados': dados['pedidos_atrasados'],
        'slug': slug,
    }

    return render(
        request,
        'Pisos/parciais/modal_painel_pedidos.html',
        context
    )