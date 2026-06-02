# services/painel_pedidos_service.py

from django.utils.timezone import now
from django.db.models import Q
from decimal import Decimal
from django.db import transaction

from Pisos.models import Pedidospisos, Itenspedidospisos
from Produtos.models import SaldoProduto


class PainelPedidosService:

    @staticmethod
    def pedidos_pendentes_compra(empr, fili=None):
        """
        Pedido pendente de compra:
        - sem data de compra workflow
        - não cancelado
        """

        filtros = Q()
        if empr:
            filtros &= Q(pedi_empr=empr)
        filtros &= Q(pedi_stat=1)

        if fili:
            filtros &= Q(pedi_fili=fili)

        return (
            Pedidospisos.objects
            .filter(filtros)
            .filter(
                Q(pedi_data_comp_work__isnull=True)
            )
            .order_by('-pedi_nume')
            .values(
                'pedi_nume',
                'pedi_clie',
                'pedi_vend',
                'pedi_fech',
                'pedi_data_prev_entr',
                'pedi_desc_comp_work',
                'pedi_empr',
                'pedi_fili',
                'pedi_stat',
            )
        )

    @staticmethod
    def pedidos_prazo_entrega_expirado(empr, fili=None):

        hoje = now().date()

        filtros = Q()
        if empr:
            filtros &= Q(pedi_empr=empr)
        filtros &= Q(pedi_data_prev_entr__gt=hoje)
        filtros &= Q(pedi_stat__gte=2)

        if fili:
            filtros &= Q(pedi_fili=fili)

        return (
            Pedidospisos.objects
            .filter(filtros)
            .order_by('pedi_data_prev_entr')
            .values(
                'pedi_nume',
                'pedi_clie',
                'pedi_vend',
                'pedi_data_prev_entr',
                'pedi_obse',
                'pedi_empr',
                'pedi_fili',
            )
        )
    
    @staticmethod
    def saldo_produto(empr, fili=None):
        """
        Saldo do produto:
        """
        filtros = Q()
        if empr:
            filtros &= Q(empresa=empr)
        
        if fili:
            filtros &= Q(filial=fili)
        
        return (
            SaldoProduto.objects
            .filter(filtros)
            .order_by('produto_codigo')
            .values(
                'produto_codigo',
                'saldo_estoque',
                'empresa',
                'filial',
            )
        )
    
    @staticmethod
    def painel_compras(empr, fili=None, pedido=None):
        """
        Painel de compras:
        - pedidos pendentes de compra
        - saldo do produto
        """
        
        pedidos_pendentes = PainelPedidosService.pedidos_pendentes_compra(empr, fili)
        saldo_produto = PainelPedidosService.saldo_produto(empr, fili)
        
        return {
            'pedidos_pendentes': list(pedidos_pendentes),
            'saldo_produto': list(saldo_produto),
        }
    
    @staticmethod
    def detalhes_pedido_compras(banco, pedido_numero, empresa, filial):
        """
        Obtém detalhes de um pedido específico para o modal de compras:
        - itens do pedido
        - saldo atual de cada produto
        - quantidade necessária
        - quantidade já comprada
        - quantidade que falta comprar
        """
        
        # Buscar itens do pedido
        itens_pedido = Itenspedidospisos.objects.using(banco).filter(
            item_empr=empresa,
            item_fili=filial,
            item_pedi=pedido_numero
        ).order_by('item_ambi', 'item_nume')
        
        itens_detalhados = []
        
        for item in itens_pedido:
            produto_codigo = item.item_prod
            quantidade_necessaria = Decimal(str(item.item_quan or 0))
            
            # Buscar saldo do produto
            try:
                saldo = SaldoProduto.objects.using(banco).get(
                    produto_codigo=produto_codigo,
                    empresa=empresa,
                    filial=filial
                )
                saldo_estoque = Decimal(str(saldo.saldo_estoque or 0))
            except SaldoProduto.DoesNotExist:
                saldo_estoque = Decimal('0')
            
            # Calcular quanto já foi comprado (baseado em quantidade entrada ou emitida)
            quantidade_comprada = Decimal(str(item.item_quan_entr or 0))
            if item.item_quan_emit:
                quantidade_comprada = max(quantidade_comprada, Decimal(str(item.item_quan_emit)))
            
            # Calcular quanto falta comprar
            quantidade_falta = max(Decimal('0'), quantidade_necessaria - quantidade_comprada)
            
            # Verificar se a compra foi efetuada
            compra_efetuada = item.item_comp_efet is not None
            data_compra = item.item_comp_efet.isoformat() if compra_efetuada else None
            
            # Verificar se está em estoque
            em_estoque = item.item_em_esto or False
            
            itens_detalhados.append({
                'produto_codigo': produto_codigo,
                'produto_nome': item.item_prod_nome or produto_codigo,
                'ambiente': item.item_ambi,
                'quantidade_necessaria': float(quantidade_necessaria),
                'saldo_estoque': float(saldo_estoque),
                'quantidade_comprada': float(quantidade_comprada),
                'quantidade_falta': float(quantidade_falta),
                'compra_efetuada': compra_efetuada,
                'data_compra': data_compra,
                'em_estoque': em_estoque,
                'item_nume': item.item_nume,
            })
        
        # Buscar dados do pedido principal
        try:
            pedido = Pedidospisos.objects.using(banco).get(
                pedi_empr=empresa,
                pedi_fili=filial,
                pedi_nume=pedido_numero
            )
            pedido_dados = {
                'numero': pedido.pedi_nume,
                'cliente': pedido.pedi_clie,
                'data': pedido.pedi_data.isoformat() if pedido.pedi_data else None,
                'data_prevista_entrega': pedido.pedi_data_prev_entr.isoformat() if pedido.pedi_data_prev_entr else None,
                'status': pedido.pedi_stat,
                'observacao_compra': pedido.pedi_desc_comp_work,
                'data_compra_workflow': pedido.pedi_data_comp_work.isoformat() if pedido.pedi_data_comp_work else None,
            }
        except Pedidospisos.DoesNotExist:
            pedido_dados = None
        
        return {
            'pedido': pedido_dados,
            'itens': itens_detalhados,
        }
    
    @staticmethod
    @transaction.atomic
    def salvar_compras(banco, pedido_numero, empresa, filial, itens_atualizados):
        """
        Atualiza as quantidades compradas dos itens do pedido:
        - Atualiza item_quan_entr com a nova quantidade comprada
        - Define item_comp_efet com a data atual se quantidade comprada > 0
        - Atualiza o status do pedido se todas as compras foram efetuadas
        """
        
        from django.utils.timezone import now
        hoje = now().date()
        
        # Buscar itens do pedido
        itens_pedido = Itenspedidospisos.objects.using(banco).filter(
            item_empr=empresa,
            item_fili=filial,
            item_pedi=pedido_numero
        )
        
        todas_compras_efetuadas = True
        
        for item_data in itens_atualizados:
            item_nume = item_data['item_nume']
            nova_qtd_comprada = Decimal(str(item_data['quantidade_comprada']))
            qtd_necessaria = Decimal(str(item_data['quantidade_necessaria']))
            
            try:
                item = itens_pedido.get(item_nume=item_nume)
                
                # Atualizar quantidade comprada
                item.item_quan_entr = nova_qtd_comprada
                
                # Se quantidade comprada > 0, marcar como compra efetuada
                if nova_qtd_comprada > 0:
                    item.item_comp_efet = hoje
                else:
                    item.item_comp_efet = None
                
                # Verificar se a compra foi totalmente efetuada
                if nova_qtd_comprada < qtd_necessaria:
                    todas_compras_efetuadas = False
                
                item.save(using=banco)
                
            except Itenspedidospisos.DoesNotExist:
                continue
        
        # Atualizar status do pedido se todas as compras foram efetuadas
        if todas_compras_efetuadas:
            try:
                pedido = Pedidospisos.objects.using(banco).get(
                    pedi_empr=empresa,
                    pedi_fili=filial,
                    pedi_nume=pedido_numero
                )
                # Atualizar data de compra workflow
                pedido.pedi_data_comp_work = hoje
                pedido.save(using=banco)
            except Pedidospisos.DoesNotExist:
                pass
        
        return {'success': True, 'message': 'Compras salvas com sucesso'}