# services/painel_pedidos_service.py

from django.utils.timezone import now
from django.db.models import Q
from decimal import Decimal
from django.db import transaction

from Pisos.models import Pedidospisos, Itenspedidospisos
from Produtos.models import SaldoProduto

# Ajuste o import abaixo conforme o app onde estão os cadastros
# de empresas/filiais no seu projeto (Licencas, Empresas, etc.)
try:
    from Licencas.models import Empresas, Filiais
except ImportError:
    Empresas = None
    Filiais = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _primeiro_campo_existente(model, candidatos):
    """
    Retorna o primeiro nome de campo que existir no model,
    dentre uma lista de candidatos. Útil porque o nome do campo
    de 'nome fantasia' varia entre projetos.
    """
    if model is None:
        return None
    nomes = {f.name for f in model._meta.get_fields()}
    for c in candidatos:
        if c in nomes:
            return c
    return None


def _mapa_nomes_empresas(banco):
    """
    Retorna {codigo_empresa: nome_fantasia} (já com strip).
    """
    if Empresas is None:
        return {}

    campo_codigo = _primeiro_campo_existente(Empresas, ['empr_codi', 'empr_id', 'id'])
    campo_nome = _primeiro_campo_existente(
        Empresas, ['empr_fant', 'empr_nome_fant', 'empr_fantasia', 'empr_nome']
    )
    if not campo_codigo or not campo_nome:
        return {}

    try:
        return {
            str(e[campo_codigo]): (e[campo_nome] or '').strip()
            for e in Empresas.objects.using(banco).values(campo_codigo, campo_nome)
        }
    except Exception:
        return {}


def _mapa_nomes_filiais(banco):
    """
    Retorna {codigo_filial: nome_fantasia} (já com strip).
    """
    if Filiais is None:
        return {}

    campo_codigo = _primeiro_campo_existente(Filiais, ['fili_codi', 'empr_codi', 'fili_id', 'id'])
    campo_nome = _primeiro_campo_existente(
        Filiais, ['fili_fant', 'fili_nome_fant', 'fili_fantasia', 'fili_nome', 'empr_fant', 'empr_nome']
    )
    if not campo_codigo or not campo_nome:
        return {}

    try:
        return {
            str(f[campo_codigo]): (f[campo_nome] or '').strip()
            for f in Filiais.objects.using(banco).values(campo_codigo, campo_nome)
        }
    except Exception:
        return {}


def _status_workflow(pedido_dict):
    """
    Determina em qual etapa do workflow o pedido está, com base
    nas datas de conclusão de cada etapa.

    Etapas (na ordem):
        1. Financeiro Ok      -> pedi_data_fina_work
        2. Compra Realizada   -> pedi_data_comp_work
        3. Pedido Instalado   -> pedi_data_inst_work
        4. Pedido Finalizado  -> pedi_data_ence_work
    """
    fina = pedido_dict.get('pedi_data_fina_work')
    comp = pedido_dict.get('pedi_data_comp_work')
    inst = pedido_dict.get('pedi_data_inst_work')
    ence = pedido_dict.get('pedi_data_ence_work')

    if ence:
        return {'texto': 'Finalizado', 'classe': 'success', 'etapa': 4}
    if inst:
        return {'texto': 'Instalado — Aguardando Finalização', 'classe': 'info', 'etapa': 3}
    if comp:
        return {'texto': 'Compra Realizada — Aguardando Instalação', 'classe': 'primary', 'etapa': 2}
    if fina:
        return {'texto': 'Financeiro OK — Aguardando Compra', 'classe': 'warning', 'etapa': 1}
    return {'texto': 'Aguardando Financeiro', 'classe': 'secondary', 'etapa': 0}


def _enriquecer_pedidos(pedidos, mapa_empresas, mapa_filiais):
    """
    Adiciona a cada pedido (dict):
        - empresa_nome / filial_nome (nome fantasia, com strip)
        - workflow (texto, classe e etapa)
    """
    enriquecidos = []
    for p in pedidos:
        p = dict(p)
        p['empresa_nome'] = mapa_empresas.get(str(p.get('pedi_empr')), '')
        p['filial_nome'] = mapa_filiais.get(str(p.get('pedi_fili')), '')
        p['workflow'] = _status_workflow(p)
        enriquecidos.append(p)
    return enriquecidos


# Campos do workflow buscados em cada query do painel.
# Ajuste aqui se os nomes no model forem diferentes.
CAMPOS_WORKFLOW = (
    'pedi_data_fina_work',
    'pedi_data_comp_work',
    'pedi_data_inst_work',
    'pedi_data_ence_work',
)


class PainelPedidosService:

    @staticmethod
    def pedidos_pendentes_compra(banco, empr, fili=None):
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
            Pedidospisos.objects.using(banco)
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
                *CAMPOS_WORKFLOW,
            )
        )

    @staticmethod
    def pedidos_prazo_entrega_expirado(banco, empr, fili=None):

        hoje = now().date()

        filtros = Q()
        if empr:
            filtros &= Q(pedi_empr=empr)
        # Prazo EXPIRADO = previsão de entrega já passou
        filtros &= Q(pedi_data_prev_entr__lt=hoje)
        filtros &= Q(pedi_stat__gte=2)

        if fili:
            filtros &= Q(pedi_fili=fili)

        return (
            Pedidospisos.objects.using(banco)
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
                'pedi_stat',
                *CAMPOS_WORKFLOW,
            )
        )

    @staticmethod
    def painel_pedidos(banco, empr, fili=None):
        """
        Monta os dados completos do painel:
        - pedidos pendentes de compra (com workflow + nomes)
        - pedidos com prazo expirado (com workflow + nomes)
        """
        mapa_empresas = _mapa_nomes_empresas(banco)
        mapa_filiais = _mapa_nomes_filiais(banco)

        pendentes = PainelPedidosService.pedidos_pendentes_compra(banco, empr, fili)
        atrasados = PainelPedidosService.pedidos_prazo_entrega_expirado(banco, empr, fili)

        return {
            'pedidos_pendentes': _enriquecer_pedidos(pendentes, mapa_empresas, mapa_filiais),
            'pedidos_atrasados': _enriquecer_pedidos(atrasados, mapa_empresas, mapa_filiais),
        }

    @staticmethod
    def saldo_produto(banco, empr, fili=None):
        """
        Saldo do produto:
        """
        filtros = Q()
        if empr:
            filtros &= Q(empresa=empr)

        if fili:
            filtros &= Q(filial=fili)

        return (
            SaldoProduto.objects.using(banco)
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
    def painel_compras(banco, empr, fili=None, pedido=None):
        """
        Painel de compras:
        - pedidos pendentes de compra
        - saldo do produto
        """

        pedidos_pendentes = PainelPedidosService.pedidos_pendentes_compra(banco, empr, fili)
        saldo_produto = PainelPedidosService.saldo_produto(banco, empr, fili)

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
    def salvar_compras(banco, pedido_numero, empresa, filial, itens_atualizados):
        """
        Atualiza as quantidades compradas dos itens do pedido:
        - Atualiza item_quan_entr com a nova quantidade comprada
        - Define item_comp_efet com a data atual se quantidade comprada > 0
        - Atualiza o status do pedido se todas as compras foram efetuadas
        """

        with transaction.atomic(using=banco):
            import logging
            logger = logging.getLogger(__name__)

            from django.utils.timezone import now
            hoje = now().date()

            logger.info(
                f"[salvar_compras] Iniciando salvamento para pedido {pedido_numero}, empresa {empresa}, filial {filial}"
            )
            logger.info(f"[salvar_compras] Itens atualizados: {itens_atualizados}")

            itens_pedido = Itenspedidospisos.objects.using(banco).filter(
                item_empr=empresa,
                item_fili=filial,
                item_pedi=pedido_numero
            )

            logger.info(f"[salvar_compras] Itens do pedido encontrados: {itens_pedido.count()}")

            todas_compras_efetuadas = True

            for item_data in itens_atualizados:
                nova_qtd_comprada = Decimal(str(item_data["quantidade_comprada"]))
                qtd_necessaria = Decimal(str(item_data["quantidade_necessaria"]))

                if item_data.get("item_nume"):
                    item_nume = item_data["item_nume"]
                    logger.info(
                        f"[salvar_compras] Processando item {item_nume}: qtd_comprada={nova_qtd_comprada}, qtd_necessaria={qtd_necessaria}"
                    )
                    try:
                        itens_pedido.get(item_nume=item_nume)
                        update_data = {"item_quan_entr": nova_qtd_comprada}

                        if nova_qtd_comprada > 0:
                            update_data["item_comp_efet"] = hoje
                            logger.info(f"[salvar_compras] Item {item_nume}: compra efetuada em {hoje}")
                        else:
                            update_data["item_comp_efet"] = None
                            logger.info(f"[salvar_compras] Item {item_nume}: compra não efetuada (qtd=0)")

                        if nova_qtd_comprada < qtd_necessaria:
                            todas_compras_efetuadas = False
                            logger.info(
                                f"[salvar_compras] Item {item_nume}: compra incompleta ({nova_qtd_comprada} < {qtd_necessaria})"
                            )
                        else:
                            logger.info(
                                f"[salvar_compras] Item {item_nume}: compra completa ({nova_qtd_comprada} >= {qtd_necessaria})"
                            )

                        Itenspedidospisos.objects.using(banco).filter(
                            item_empr=empresa,
                            item_fili=filial,
                            item_pedi=pedido_numero,
                            item_nume=item_nume,
                        ).update(**update_data)
                        logger.info(f"[salvar_compras] Item {item_nume}: salvo com sucesso")
                    except Itenspedidospisos.DoesNotExist:
                        logger.error(f"[salvar_compras] Item {item_nume}: não encontrado no pedido")
                        todas_compras_efetuadas = False
                        continue
                else:
                    item_ambi = item_data.get("item_ambi")
                    item_prod = item_data.get("item_prod")
                    logger.info(
                        f"[salvar_compras] Processando item por ambiente+produto: ambi={item_ambi}, prod={item_prod}, qtd_comprada={nova_qtd_comprada}"
                    )

                    update_data = {"item_quan_entr": nova_qtd_comprada}

                    if nova_qtd_comprada > 0:
                        update_data["item_comp_efet"] = hoje
                        logger.info(f"[salvar_compras] Item ambi={item_ambi}, prod={item_prod}: compra efetuada em {hoje}")
                    else:
                        update_data["item_comp_efet"] = None
                        logger.info(f"[salvar_compras] Item ambi={item_ambi}, prod={item_prod}: compra não efetuada (qtd=0)")

                    if nova_qtd_comprada < qtd_necessaria:
                        todas_compras_efetuadas = False
                        logger.info(
                            f"[salvar_compras] Item ambi={item_ambi}, prod={item_prod}: compra incompleta ({nova_qtd_comprada} < {qtd_necessaria})"
                        )
                    else:
                        logger.info(
                            f"[salvar_compras] Item ambi={item_ambi}, prod={item_prod}: compra completa ({nova_qtd_comprada} >= {qtd_necessaria})"
                        )

                    updated = itens_pedido.filter(item_ambi=item_ambi, item_prod=item_prod).update(**update_data)
                    if updated == 0:
                        logger.error(
                            f"[salvar_compras] Item com ambi={item_ambi}, prod={item_prod}: não encontrado no pedido (0 linhas atualizadas)"
                        )
                        todas_compras_efetuadas = False
                    else:
                        logger.info(
                            f"[salvar_compras] Item ambi={item_ambi}, prod={item_prod}: {updated} linha(s) atualizada(s) com sucesso"
                        )

            logger.info(f"[salvar_compras] Todas as compras efetuadas: {todas_compras_efetuadas}")

            if todas_compras_efetuadas:
                try:
                    Pedidospisos.objects.using(banco).filter(
                        pedi_empr=empresa,
                        pedi_fili=filial,
                        pedi_nume=pedido_numero,
                    ).update(pedi_data_comp_work=hoje)
                    logger.info(f"[salvar_compras] Pedido {pedido_numero}: data_compra_workflow atualizada para {hoje}")
                except Pedidospisos.DoesNotExist:
                    logger.error(f"[salvar_compras] Pedido {pedido_numero}: não encontrado")
                    pass
            else:
                logger.info(
                    f"[salvar_compras] Pedido {pedido_numero}: nem todas as compras foram efetuadas, não atualizando data_compra_workflow"
                )

            logger.info(f"[salvar_compras] Salvamento concluído com sucesso para pedido {pedido_numero}")
            return {"success": True, "message": "Compras salvas com sucesso"}