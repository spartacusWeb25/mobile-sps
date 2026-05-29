# views/painel_pedidos_view.py

from django.shortcuts import render
from Pisos.services.painel_gestao_compras_pisos import PainelPedidosService


def modal_painel_pedidos(request, slug):

    empresa = request.session.get('empresa')
    filial = request.session.get('filial')

    # Fallback: aceitar empresa/filial via GET params caso a sessão esteja vazia
    req_empresa = request.GET.get('empresa') or empresa
    req_filial = request.GET.get('filial') or filial

    print('modal_painel_pedidos: empresa(session) =', empresa, 'filial(session) =', filial)
    print('modal_painel_pedidos: empresa(used) =', req_empresa, 'filial(used) =', req_filial)

    pedidos_pendentes = (
        PainelPedidosService
        .pedidos_pendentes_compra(req_empresa, req_filial)
    )
    print('pedidos_pendentes ->', pedidos_pendentes)

    pedidos_atrasados = (
        PainelPedidosService
        .pedidos_prazo_entrega_expirado(req_empresa, req_filial)
    )
    print('pedidos_atrasados ->', pedidos_atrasados)

    context = {
        'pedidos_pendentes': pedidos_pendentes,
        'pedidos_atrasados': pedidos_atrasados,
        'slug': slug,
    }

    return render(
        request,
        'Pisos/parciais/modal_painel_pedidos.html',
        context
    )