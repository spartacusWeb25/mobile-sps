from django.db import transaction, models
from django.core.exceptions import ValidationError
from .models import Titulosreceber, Baretitulos
from decimal import Decimal
from calendar import monthrange
from datetime import date
from Entidades.models import Entidades
from Lancamentos_Bancarios.models import Lctobancario
from Lancamentos_Bancarios.utils import get_next_lcto_number
from adiantamentos.services import AdiantamentosService
from CentrodeCustos.models import Centrodecustos


def _validar_campos_obrigatorios(dados):
    obrigatorios = ['titu_empr','titu_fili','titu_clie','titu_titu','titu_seri','titu_parc','titu_emis','titu_venc','titu_valo']
    erros = {}
    for campo in obrigatorios:
        if dados.get(campo) in [None, '', []]:
            erros[campo] = ['Campo obrigatório.']
    if erros:
        raise ValidationError(erros)


def _add_months(d: date, m: int) -> date:
    y = d.year + (d.month - 1 + m) // 12
    mo = (d.month - 1 + m) % 12 + 1
    last = monthrange(y, mo)[1]
    day = d.day if d.day <= last else last
    return date(y, mo, day)


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def _parcela_sort_key(value) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _filtro_titulo(obj: Titulosreceber) -> dict:
    return {
        'titu_empr': obj.titu_empr,
        'titu_fili': obj.titu_fili,
        'titu_clie': obj.titu_clie,
        'titu_titu': obj.titu_titu,
        'titu_seri': obj.titu_seri,
        'titu_parc': obj.titu_parc,
        'titu_emis': obj.titu_emis,
        'titu_venc': obj.titu_venc,
    }


def _filtro_pk_titulo(obj: Titulosreceber) -> dict:
    return {
        'titu_empr': obj.titu_empr,
        'titu_fili': obj.titu_fili,
        'titu_clie': obj.titu_clie,
        'titu_titu': obj.titu_titu,
        'titu_seri': obj.titu_seri,
        'titu_parc': obj.titu_parc,
    }


def _tmp_parcela(idx: int) -> str:
    if idx < 1 or idx > 1295:
        raise ValidationError({'detail': ['Quantidade de parcelas inválida para reorganização.']})
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    high = idx // 36
    low = idx % 36
    return f"Z{alphabet[high]}{alphabet[low]}"


def _campos_replicados_titulo(titulo: Titulosreceber) -> dict:
    return {
        'titu_cont': titulo.titu_cont,
        'titu_cecu': titulo.titu_cecu,
        'titu_even': titulo.titu_even,
        'titu_prov': titulo.titu_prov,
        'titu_hist': titulo.titu_hist,
        'titu_aber': titulo.titu_aber or 'A',
        'titu_ctrl': titulo.titu_ctrl,
        'titu_form_reci': titulo.titu_form_reci,
        'titu_tipo': titulo.titu_tipo,
        'titu_port': titulo.titu_port,
        'titu_situ': titulo.titu_situ,
    }


def _gerar_parcelas_padrao(*, quantidade: int, total: Decimal, vencimento_inicial: date) -> list[dict]:
    base = (total / Decimal(quantidade)).quantize(Decimal('0.01'))
    diferenca = total - (base * quantidade)
    parcelas = []
    for i in range(1, quantidade + 1):
        valor = base if i < quantidade else base + diferenca
        parcelas.append({
            'parcela': str(i),
            'vencimento': _add_months(vencimento_inicial, i - 1),
            'valor': _money(valor),
        })
    return parcelas


def _normalizar_parcelas_planejadas(
    parcelas_planejadas,
    *,
    quantidade_padrao: int,
    total_esperado: Decimal,
    vencimento_inicial: date,
) -> list[dict]:
    total_esperado = _money(total_esperado)
    if not parcelas_planejadas:
        return _gerar_parcelas_padrao(
            quantidade=quantidade_padrao,
            total=total_esperado,
            vencimento_inicial=vencimento_inicial,
        )

    normalizadas = []
    for indice, item in enumerate(parcelas_planejadas, start=1):
        if not isinstance(item, dict):
            raise ValidationError({'detail': ['Cronograma de parcelas inválido.']})

        parcela = str(item.get('parcela') or indice).strip()
        valor = _money(item.get('valor'))
        vencimento = item.get('vencimento')

        if not parcela:
            raise ValidationError({'detail': [f'Parcela {indice} sem identificação.']})
        if valor <= 0:
            raise ValidationError({'detail': [f'Parcela {parcela} com valor inválido.']})
        if isinstance(vencimento, str):
            try:
                vencimento = date.fromisoformat(vencimento)
            except ValueError as exc:
                raise ValidationError({'detail': [f'Parcela {parcela} com vencimento inválido.']}) from exc
        if not isinstance(vencimento, date):
            raise ValidationError({'detail': [f'Parcela {parcela} com vencimento inválido.']})

        normalizadas.append({
            'parcela': parcela,
            'vencimento': vencimento,
            'valor': valor,
        })

    normalizadas.sort(key=lambda item: _parcela_sort_key(item['parcela']))
    esperadas = [str(i) for i in range(1, len(normalizadas) + 1)]
    atuais = [item['parcela'] for item in normalizadas]
    if atuais != esperadas:
        raise ValidationError({'detail': ['As parcelas devem ser sequenciais a partir de 1.']})

    total_informado = sum((item['valor'] for item in normalizadas), Decimal('0.00')).quantize(Decimal('0.01'))
    if total_informado != total_esperado:
        raise ValidationError({
            'detail': [
                f'Total das parcelas ({total_informado}) difere do valor total informado ({total_esperado}).'
            ]
        })

    return normalizadas

def criar_titulo_receber(*, banco: str, dados: dict, empresa_id: int, filial_id: int) -> Titulosreceber:
    if not dados.get('titu_empr'):
        dados['titu_empr'] = empresa_id
    if not dados.get('titu_fili'):
        dados['titu_fili'] = filial_id
    _validar_campos_obrigatorios(dados)
    with transaction.atomic(using=banco):
        existe = Titulosreceber.objects.using(banco).filter(
            titu_empr=dados['titu_empr'] or empresa_id,
            titu_fili=dados['titu_fili'] or filial_id,
            titu_clie=dados['titu_clie'],
            titu_titu=dados['titu_titu'],
            titu_seri=dados['titu_seri'],
            titu_parc=dados['titu_parc'],
            titu_emis=dados['titu_emis'],
            titu_venc=dados['titu_venc'],
        ).exists()
        if existe:
            raise ValidationError({'detail': ['Título já existe.']})
        dados.setdefault('titu_aber', 'A')
        obj = Titulosreceber.objects.using(banco).create(**dados)
        return obj

def atualizar_titulo_receber(titulo: Titulosreceber, *, banco: str, dados: dict) -> Titulosreceber:
    _validar_campos_obrigatorios({**{
        'titu_empr': getattr(titulo, 'titu_empr', None),
        'titu_fili': getattr(titulo, 'titu_fili', None),
        'titu_clie': titulo.titu_clie,
        'titu_titu': titulo.titu_titu,
        'titu_seri': titulo.titu_seri,
        'titu_parc': titulo.titu_parc,
        'titu_emis': titulo.titu_emis,
        'titu_venc': titulo.titu_venc,
        'titu_valo': titulo.titu_valo,
    }, **dados})
    with transaction.atomic(using=banco):
        # PATCH: atualizar somente campos não-chave, usando filtro pela chave composta
        chaves = {'titu_empr','titu_fili','titu_clie','titu_titu','titu_seri','titu_parc'}
        updates = {k: v for k, v in dados.items() if k not in chaves}
        if updates:
            (Titulosreceber.objects
                .using(banco)
                .filter(
                    titu_empr=getattr(titulo, 'titu_empr'),
                    titu_fili=getattr(titulo, 'titu_fili'),
                    titu_clie=titulo.titu_clie,
                    titu_titu=titulo.titu_titu,
                    titu_seri=titulo.titu_seri,
                    titu_parc=titulo.titu_parc,
                )
                .update(**updates)
            )
        # Recarrega objeto atualizado
        return (Titulosreceber.objects
                .using(banco)
                .filter(
                    titu_empr=getattr(titulo, 'titu_empr'),
                    titu_fili=getattr(titulo, 'titu_fili'),
                    titu_clie=titulo.titu_clie,
                    titu_titu=titulo.titu_titu,
                    titu_seri=titulo.titu_seri,
                    titu_parc=titulo.titu_parc,
                )
                .first())

def excluir_titulo_receber(titulo: Titulosreceber, *, banco: str) -> None:
    with transaction.atomic(using=banco):
        titulo.delete(using=banco)


def gera_parcelas_a_receber(titulo: Titulosreceber, *, banco: str, parcelas_planejadas=None) -> None:
    with transaction.atomic(using=banco):
        quantidade = int(str(titulo.titu_parc))
        parcelas = _normalizar_parcelas_planejadas(
            parcelas_planejadas,
            quantidade_padrao=quantidade,
            total_esperado=_money(titulo.titu_valo),
            vencimento_inicial=titulo.titu_venc,
        )
        filtro_original = _filtro_titulo(titulo)
        primeira = parcelas[0]
        Titulosreceber.objects.using(banco).filter(**filtro_original).update(
            titu_parc=primeira['parcela'],
            titu_venc=primeira['vencimento'],
            titu_valo=primeira['valor'],
            titu_cecu=titulo.titu_cecu,
        )

        campos_replicados = _campos_replicados_titulo(titulo)
        for item in parcelas[1:]:
            Titulosreceber.objects.using(banco).create(
                titu_empr=titulo.titu_empr,
                titu_fili=titulo.titu_fili,
                titu_clie=titulo.titu_clie,
                titu_titu=titulo.titu_titu,
                titu_seri=titulo.titu_seri,
                titu_parc=item['parcela'],
                titu_emis=titulo.titu_emis,
                titu_venc=item['vencimento'],
                titu_valo=item['valor'],
                **campos_replicados,
            )


def atualizar_grupo_parcelas_receber(
    titulo: Titulosreceber,
    *,
    banco: str,
    dados: dict,
    parcelas_planejadas=None,
) -> list[Titulosreceber]:
    with transaction.atomic(using=banco):
        grupo = list(
            Titulosreceber.objects.using(banco)
            .filter(
                titu_empr=titulo.titu_empr,
                titu_fili=titulo.titu_fili,
                titu_clie=titulo.titu_clie,
                titu_titu=titulo.titu_titu,
                titu_seri=titulo.titu_seri,
            )
            .order_by('titu_parc', 'titu_venc')
        )
        if not grupo:
            raise ValidationError({'detail': ['Grupo de parcelas não encontrado.']})

        if any((item.titu_aber or 'A') != 'A' for item in grupo):
            raise ValueError('Somente grupos com parcelas em aberto podem ser reorganizados.')

        parcelas = _normalizar_parcelas_planejadas(
            parcelas_planejadas,
            quantidade_padrao=int(str(dados['titu_parc'])),
            total_esperado=_money(dados.get('titu_valo')),
            vencimento_inicial=dados.get('titu_venc'),
        )

        campos_comuns = {
            'titu_emis': dados.get('titu_emis'),
            'titu_form_reci': dados.get('titu_form_reci'),
            'titu_cecu': dados.get('titu_cecu'),
        }

        tmp_ids = []
        for idx, atual in enumerate(grupo, start=1):
            tmp = _tmp_parcela(idx)
            Titulosreceber.objects.using(banco).filter(**_filtro_pk_titulo(atual)).update(titu_parc=tmp)
            atual.titu_parc = tmp
            tmp_ids.append(tmp)

        atualizados = []
        reutilizar = min(len(grupo), len(parcelas))
        for indice, item in enumerate(parcelas):
            payload = {
                'titu_parc': item['parcela'],
                'titu_emis': campos_comuns['titu_emis'],
                'titu_venc': item['vencimento'],
                'titu_valo': item['valor'],
                'titu_form_reci': campos_comuns['titu_form_reci'],
                'titu_cecu': campos_comuns['titu_cecu'],
            }
            if indice < reutilizar:
                atual = grupo[indice]
                Titulosreceber.objects.using(banco).filter(**_filtro_pk_titulo(atual)).update(**payload)
            else:
                atual = Titulosreceber.objects.using(banco).create(
                    titu_empr=titulo.titu_empr,
                    titu_fili=titulo.titu_fili,
                    titu_clie=titulo.titu_clie,
                    titu_titu=titulo.titu_titu,
                    titu_seri=titulo.titu_seri,
                    titu_aber='A',
                    titu_cont=titulo.titu_cont,
                    titu_even=titulo.titu_even,
                    titu_prov=titulo.titu_prov,
                    titu_hist=titulo.titu_hist,
                    titu_ctrl=titulo.titu_ctrl,
                    titu_tipo=titulo.titu_tipo,
                    titu_port=titulo.titu_port,
                    titu_situ=titulo.titu_situ,
                    **payload,
                )
                atualizados.append(atual)
                continue

            atual.titu_parc = payload['titu_parc']
            atual.titu_emis = payload['titu_emis']
            atual.titu_venc = payload['titu_venc']
            atual.titu_valo = payload['titu_valo']
            atual.titu_form_reci = payload['titu_form_reci']
            atual.titu_cecu = payload['titu_cecu']
            atualizados.append(atual)

        excedentes_tmp = tmp_ids[len(parcelas):]
        if excedentes_tmp:
            Titulosreceber.objects.using(banco).filter(
                titu_empr=titulo.titu_empr,
                titu_fili=titulo.titu_fili,
                titu_clie=titulo.titu_clie,
                titu_titu=titulo.titu_titu,
                titu_seri=titulo.titu_seri,
                titu_parc__in=excedentes_tmp,
            ).delete()

        atualizados.sort(key=lambda item: _parcela_sort_key(item.titu_parc))
        return atualizados


def _resolver_banco_recebimento(titulo: Titulosreceber, *, banco: str, dados: dict) -> int:
    if dados.get('banco') is not None:
        banco_id = int(dados['banco'])
        existe = Entidades.objects.using(banco).filter(
            enti_empr=titulo.titu_empr,
            enti_clie=banco_id,
        ).exists()
        if not existe:
            raise ValueError("Banco/caixa informado não existe para esta empresa.")
        return banco_id

    ultima = (
        Baretitulos.objects.using(banco)
        .filter(
            bare_empr=titulo.titu_empr,
            bare_fili=titulo.titu_fili,
            bare_clie=titulo.titu_clie,
            bare_titu=titulo.titu_titu,
            bare_seri=titulo.titu_seri,
            bare_parc=titulo.titu_parc,
        )
        .exclude(bare_banc__isnull=True)
        .order_by('-bare_sequ')
        .first()
    )
    if ultima and ultima.bare_banc is not None:
        return int(ultima.bare_banc)

    caixa = (
        Entidades.objects.using(banco)
        .filter(enti_empr=titulo.titu_empr, enti_tien='C')
        .order_by('enti_clie')
        .first()
    )
    if not caixa:
        raise ValueError("Nenhum caixa padrão configurado para esta empresa.")
    return int(caixa.enti_clie)


def _resolver_centro_custo_recebimento(titulo: Titulosreceber, *, banco: str, dados: dict) -> int | None:
    if dados.get('centro_custo') is not None:
        cecu_redu = int(dados['centro_custo'])
        existe = Centrodecustos.objects.using(banco).filter(
            cecu_empr=titulo.titu_empr,
            cecu_redu=cecu_redu,
        ).exists()
        if not existe:
            raise ValueError("Centro de custo informado não existe para esta empresa.")
        return cecu_redu
    return int(titulo.titu_cecu) if titulo.titu_cecu is not None else None


def _calcular_valor_ja_recebido(titulo: Titulosreceber, *, banco: str) -> Decimal:
    if titulo.titu_aber != 'P':
        return Decimal('0')

    agg = Baretitulos.objects.using(banco).filter(
        bare_empr=titulo.titu_empr,
        bare_fili=titulo.titu_fili,
        bare_clie=titulo.titu_clie,
        bare_titu=titulo.titu_titu,
        bare_seri=titulo.titu_seri,
        bare_parc=titulo.titu_parc,
    ).aggregate(
        total_valo_pago=models.Sum('bare_valo_pago'),
        total_sub_tota=models.Sum('bare_sub_tota'),
    )
    return Decimal(str(agg['total_valo_pago'] or agg['total_sub_tota'] or 0))


def _calcular_valor_total_baixas(titulo: Titulosreceber, *, banco: str) -> Decimal:
    agg = Baretitulos.objects.using(banco).filter(
        bare_empr=titulo.titu_empr,
        bare_fili=titulo.titu_fili,
        bare_clie=titulo.titu_clie,
        bare_titu=titulo.titu_titu,
        bare_seri=titulo.titu_seri,
        bare_parc=titulo.titu_parc,
    ).aggregate(
        total_valo_pago=models.Sum('bare_valo_pago'),
        total_sub_tota=models.Sum('bare_sub_tota'),
    )
    return Decimal(str(agg['total_valo_pago'] or agg['total_sub_tota'] or 0))


def _next_bare_sequ(banco: str) -> int:
    ultimo = Baretitulos.objects.using(banco).order_by('-bare_sequ').first()
    return (ultimo.bare_sequ + 1) if ultimo else 1


def _atualizar_status_titulo(titulo: Titulosreceber, novo_status: str, *, banco: str) -> None:
    Titulosreceber.objects.using(banco).filter(
        titu_empr=titulo.titu_empr,
        titu_fili=titulo.titu_fili,
        titu_clie=titulo.titu_clie,
        titu_titu=titulo.titu_titu,
        titu_seri=titulo.titu_seri,
        titu_parc=titulo.titu_parc,
        titu_emis=titulo.titu_emis,
        titu_venc=titulo.titu_venc,
    ).update(titu_aber=novo_status)


def _gerar_lancamento_bancario_recebimento(
    titulo: Titulosreceber,
    baixa: Baretitulos,
    *,
    banco: str,
) -> Lctobancario:
    if baixa.bare_banc is None:
        raise ValueError("Baixa sem banco definido — não é possível gerar lançamento bancário.")

    return Lctobancario.objects.using(banco).create(
        laba_ctrl=get_next_lcto_number(titulo.titu_empr, titulo.titu_fili, banco),
        laba_empr=titulo.titu_empr,
        laba_fili=titulo.titu_fili,
        laba_banc=int(baixa.bare_banc),
        laba_data=baixa.bare_dpag,
        laba_cecu=baixa.bare_cecu,
        laba_valo=baixa.bare_sub_tota or baixa.bare_pago,
        laba_hist=baixa.bare_hist,
        laba_dbcr='C',
        laba_enti=titulo.titu_clie,
        laba_cheq=baixa.bare_cheq,
    )


def baixar_titulo_receber(
    titulo: Titulosreceber,
    *,
    banco: str,
    dados: dict,
    usuario_id: int | None = None,
) -> tuple[Baretitulos, Lctobancario | None]:
    with transaction.atomic(using=banco):
        if titulo.titu_aber == 'T':
            raise ValueError("Título já está totalmente baixado.")

        valor_titulo = Decimal(str(titulo.titu_valo or 0))
        valor_recebido = Decimal(str(dados['valor_recebido']))
        valor_juros = Decimal(str(dados.get('valor_juros') or 0))
        valor_multa = Decimal(str(dados.get('valor_multa') or 0))
        valor_desconto = Decimal(str(dados.get('valor_desconto') or 0))
        valor_liquido = valor_recebido + valor_juros + valor_multa - valor_desconto

        valor_ja_recebido = _calcular_valor_ja_recebido(titulo, banco=banco)
        valor_acumulado = valor_ja_recebido + valor_liquido
        tipo_baixa = 'T' if valor_acumulado >= valor_titulo else 'P'

        adiantamento_usado = None
        if dados.get('forma_pagamento') == 'A':
            adiantamento_usado = AdiantamentosService.usar_adiantamento_by_context(
                empresa=titulo.titu_empr,
                filial=titulo.titu_fili,
                entidade=titulo.titu_clie,
                tipo='R',
                valor=valor_recebido,
                using=banco,
                referencia={
                    'modulo': 'contas_a_receber',
                    'titu': titulo.titu_titu,
                    'seri': titulo.titu_seri,
                    'parc': titulo.titu_parc,
                },
            )

        banco_resolvido = _resolver_banco_recebimento(titulo, banco=banco, dados=dados)
        cecu_resolvido = _resolver_centro_custo_recebimento(titulo, banco=banco, dados=dados)

        baixa = Baretitulos.objects.using(banco).create(
            bare_sequ=_next_bare_sequ(banco),
            bare_ctrl=titulo.titu_ctrl or 0,
            bare_empr=titulo.titu_empr,
            bare_fili=titulo.titu_fili,
            bare_clie=titulo.titu_clie,
            bare_titu=titulo.titu_titu,
            bare_seri=titulo.titu_seri,
            bare_parc=titulo.titu_parc,
            bare_dpag=dados['data_recebimento'],
            bare_apag=valor_titulo,
            bare_vmul=valor_multa,
            bare_vjur=valor_juros,
            bare_vdes=valor_desconto,
            bare_pago=valor_liquido,
            bare_valo_pago=valor_recebido,
            bare_sub_tota=valor_liquido,
            bare_topa=tipo_baixa,
            bare_form=dados.get('forma_pagamento', 'D'),
            bare_banc=banco_resolvido,
            bare_cheq=dados.get('cheque'),
            bare_hist=dados.get('historico') or f'Baixa do título {titulo.titu_titu}',
            bare_emis=titulo.titu_emis,
            bare_venc=titulo.titu_venc,
            bare_cont=titulo.titu_cont,
            bare_cecu=cecu_resolvido,
            bare_even=titulo.titu_even,
            bare_port=titulo.titu_port,
            bare_situ=titulo.titu_situ,
            bare_id_adto=int(adiantamento_usado.adia_docu) if adiantamento_usado else None,
            bare_usua_baix=usuario_id,
            bare_data_baix=dados['data_recebimento'],
        )

        _atualizar_status_titulo(titulo, tipo_baixa, banco=banco)

        lancamento = None
        if baixa.bare_form == 'B':
            lancamento = _gerar_lancamento_bancario_recebimento(titulo, baixa, banco=banco)
            Baretitulos.objects.using(banco).filter(
                bare_sequ=baixa.bare_sequ,
                bare_empr=baixa.bare_empr,
                bare_fili=baixa.bare_fili,
                bare_clie=baixa.bare_clie,
                bare_titu=baixa.bare_titu,
                bare_seri=baixa.bare_seri,
                bare_parc=baixa.bare_parc,
            ).update(
                bare_ctrl_banc=lancamento.laba_ctrl,
                bare_lote_banc=lancamento.laba_lote,
                bare_sequ_banc=lancamento.laba_ctrl,
            )

        return baixa, lancamento


def excluir_baixa_receber(
    titulo: Titulosreceber,
    baixa_id: int,
    *,
    banco: str,
) -> dict:
    with transaction.atomic(using=banco):
        baixa = Baretitulos.objects.using(banco).get(
            bare_sequ=baixa_id,
            bare_empr=titulo.titu_empr,
            bare_fili=titulo.titu_fili,
            bare_clie=titulo.titu_clie,
            bare_titu=titulo.titu_titu,
            bare_seri=titulo.titu_seri,
            bare_parc=titulo.titu_parc,
        )

        valor_baixa = baixa.bare_valo_pago or baixa.bare_sub_tota or Decimal('0')
        if baixa.bare_form in ('A', 'P') and valor_baixa > 0:
            AdiantamentosService.estornar_adiantamento_by_context(
                empresa=titulo.titu_empr,
                filial=titulo.titu_fili,
                entidade=titulo.titu_clie,
                tipo='R',
                valor=valor_baixa,
                using=banco,
            )

        if baixa.bare_ctrl_banc:
            filtros = {
                'laba_empr': baixa.bare_empr,
                'laba_fili': baixa.bare_fili,
                'laba_ctrl': int(baixa.bare_ctrl_banc),
            }
            if baixa.bare_banc is not None:
                filtros['laba_banc'] = int(baixa.bare_banc)
            Lctobancario.objects.using(banco).filter(**filtros).delete()
            logger.info(f"Lançamento bancário {baixa.bare_ctrl_banc} excluído para baixa {baixa.bare_sequ}")

        baixa.delete()

        total_restante = _calcular_valor_total_baixas(titulo, banco=banco)
        valor_titulo = Decimal(str(titulo.titu_valo or 0))

        if total_restante <= 0:
            novo_status = 'A'
        elif total_restante >= valor_titulo:
            novo_status = 'T'
        else:
            novo_status = 'P'

        _atualizar_status_titulo(titulo, novo_status, banco=banco)

        return {
            'baixa_excluida': baixa_id,
            'novo_status_titulo': novo_status,
        }


def reabrir_titulo_receber_sem_baixa(
    titulo: Titulosreceber,
    *,
    banco: str,
) -> dict:
    with transaction.atomic(using=banco):
        existe_baixa = Baretitulos.objects.using(banco).filter(
            bare_empr=titulo.titu_empr,
            bare_fili=titulo.titu_fili,
            bare_clie=titulo.titu_clie,
            bare_titu=titulo.titu_titu,
            bare_seri=titulo.titu_seri,
            bare_parc=titulo.titu_parc,
        ).exists()
        if existe_baixa:
            raise ValueError("Este título possui baixas registradas; use a reabertura via exclusão de baixa.")

        _atualizar_status_titulo(titulo, 'A', banco=banco)
        return {'novo_status_titulo': 'A'}
