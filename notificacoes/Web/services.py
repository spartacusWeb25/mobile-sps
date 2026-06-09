from django.db.models import Sum, Q
from datetime import date, timedelta
from Entidades.models import Entidades  
import base64
from django.utils import timezone

def _local_today():
    now = timezone.now()

    if timezone.is_naive(now):
        return now.date()

    return timezone.localtime(now).date()


def get_filial_logo(db_alias, empresa_id, filial_id):
    """
    Get filial logo from database and convert to base64
    """
    try:
        from Licencas.models import Filiais
        filial = Filiais.objects.using(db_alias).filter(
            empr_empr=empresa_id,
            empr_codi=filial_id
        ).first()
        if filial and filial.empr_logo:
            # Se for bytes (BinaryField), converte para base64
            logo_data = filial.empr_logo
            if isinstance(logo_data, memoryview):
                logo_data = logo_data.tobytes()
            if isinstance(logo_data, bytes):
                return base64.b64encode(logo_data).decode('utf-8')
    except Exception:
        pass
    return None


def prepare_pagar_print_data(db_alias, empresa_id, filial_id, period='hoje', status=None, vencimento_inicial=None, vencimento_final=None):
    """
    Prepare data for accounts payable print view
    """
    from contas_a_pagar.models import Titulospagar, Bapatitulos
    from Licencas.models import Empresas, Filiais
    from datetime import datetime
    
    today = _local_today()
    venc_ini = None
    venc_fim = None
    try:
        if vencimento_inicial:
            venc_ini = date.fromisoformat(str(vencimento_inicial).strip())
    except Exception:
        venc_ini = None
    try:
        if vencimento_final:
            venc_fim = date.fromisoformat(str(vencimento_final).strip())
    except Exception:
        venc_fim = None
    usar_intervalo = bool(venc_ini or venc_fim)
    
    print(f"DEBUG: prepare_pagar_print_data called with empresa_id={empresa_id}, filial_id={filial_id}, period={period}, status={status}")
    
    # Get empresa and filial info (for display purposes only)
    empresa_info = Empresas.objects.using(db_alias).filter(empr_codi=empresa_id).first()
    filial_info = Filiais.objects.using(db_alias).filter(
        empr_empr=empresa_id,
        empr_codi=filial_id
    ).first()
    
    print(f"DEBUG: empresa_info={empresa_info}, filial_info={filial_info}")
    
    # Get suppliers from all companies
    fornecedores = dict(
        Entidades.objects.using(db_alias)
        .all()
        .values_list('enti_clie', 'enti_nome')
    )
    
    # Get titles - filter by provided empresa_id and filial_id (like list view). If empresa_id/filial_id is None include ALL.
    if status == 'quitado':
        # use date ranges (date objects)
        w_start_date = today - timedelta(days=today.weekday())
        w_end_date = w_start_date + timedelta(days=6)
        d_start_date = today
        d_end_date = today + timedelta(days=1)
        print(f"DEBUG: quitado mode - d_start={d_start_date}, d_end={d_end_date}, w_start={w_start_date}, w_end={w_end_date}")
        qs = Bapatitulos.objects.using(db_alias).all()
        # apply company/filial filters only when provided
        if empresa_id:
            qs = qs.filter(bapa_empr=empresa_id)
        if filial_id:
            qs = qs.filter(bapa_fili=filial_id)
        if usar_intervalo:
            if venc_ini:
                qs = qs.filter(bapa_venc__gte=venc_ini)
            if venc_fim:
                qs = qs.filter(bapa_venc__lte=venc_fim)
            qs = qs.order_by('bapa_empr', 'bapa_fili', 'bapa_venc', 'bapa_titu')
        else:
            if period == 'semana':
                qs = qs.filter(bapa_dpag__gte=w_start_date, bapa_dpag__lt=w_end_date + timedelta(days=1))
            else:
                qs = qs.filter(bapa_dpag__gte=d_start_date, bapa_dpag__lt=d_end_date)
            qs = qs.order_by('bapa_empr', 'bapa_fili', 'bapa_dpag', 'bapa_titu')
    else:
        qs = Titulospagar.objects.using(db_alias).all()
        # apply company/filial filters only when provided
        if empresa_id:
            qs = qs.filter(titu_empr=empresa_id)
        if filial_id:
            qs = qs.filter(titu_fili=filial_id)
        qs = qs.filter(
            (Q(titu_emis__isnull=True) | Q(titu_emis__gte=date(1900,1,1))),
            (Q(titu_venc__isnull=True) | Q(titu_venc__gte=date(1900,1,1))),
        )
        if usar_intervalo:
            if venc_ini:
                qs = qs.filter(titu_venc__gte=venc_ini)
            if venc_fim:
                qs = qs.filter(titu_venc__lte=venc_fim)
        else:
            if period == 'semana':
                w_start_date = today - timedelta(days=today.weekday())
                w_end_date = w_start_date + timedelta(days=6)
                print(f"DEBUG: semana mode - w_start={w_start_date}, w_end={w_end_date}")
                qs = qs.filter(titu_venc__gte=w_start_date, titu_venc__lt=w_end_date + timedelta(days=1))
            else:
                d_start_date = today
                d_end_date = today + timedelta(days=1)
                print(f"DEBUG: hoje mode - d_start={d_start_date}, d_end={d_end_date}")
                qs = qs.filter(titu_venc__gte=d_start_date, titu_venc__lt=d_end_date)
        if status == 'aberto':
            qs = qs.filter(titu_aber='A')
        qs = qs.order_by('titu_empr', 'titu_fili', 'titu_forn', 'titu_venc', 'titu_titu')
    
    print(f"DEBUG: qs count={qs.count()}")
    
    # Prepare data
    import re
    data = []
    total_sum = 0
    logo_cache = {}
    empresas_totals = {}
    filial_totals = {}  # {empresa_id: {filial_id: {'nome':..., 'valor':..., 'count':...}}}

    for o in qs:
        forn = getattr(o, 'titu_forn', '') or getattr(o, 'bapa_forn', '')
        valo = getattr(o, 'titu_valo', '') or getattr(o, 'bapa_valo', '') or getattr(o, 'bapa_valo_pago', '')
        parc = getattr(o, 'titu_parc', '') or getattr(o, 'bapa_parc', '')
        venc = getattr(o, 'titu_venc', '') or getattr(o, 'bapa_venc', '')
        dpag = getattr(o, 'bapa_dpag', '')
        aber = 'T' if status == 'quitado' else getattr(o, 'titu_aber', '')

        # company/filial ids for grouping
        row_empresa_id = getattr(o, 'titu_empr', '') or getattr(o, 'bapa_empr', '')
        row_filial_id = getattr(o, 'titu_fili', '') or getattr(o, 'bapa_fili', '')

        row_empresa_info = None
        row_filial_info = None
        try:
            if row_empresa_id:
                row_empresa_info = Empresas.objects.using(db_alias).filter(empr_codi=row_empresa_id).first()
            if row_filial_id and row_empresa_info:
                row_filial_info = Filiais.objects.using(db_alias).filter(empr_empr=row_empresa_id, empr_codi=row_filial_id).first()
        except Exception:
            pass

        # prepare display names
        empresa_raw = getattr(row_empresa_info, 'empr_nome', '') if row_empresa_info else ''
        m = re.search(r"\bltda\b", empresa_raw, flags=re.IGNORECASE)
        empresa_display = empresa_raw[:m.end()].strip() if m else empresa_raw
        filial_display = (getattr(row_filial_info, 'empr_fant', '') or getattr(row_filial_info, 'empr_nome', '')) if row_filial_info else ''

        # sum
        try:
            val_float = float(valo) if valo else 0.0
        except Exception:
            val_float = 0.0
        total_sum += val_float

        # get filial logo cached
        filial_logo = None
        try:
            if row_empresa_id and row_filial_id:
                logo_key = f"{row_empresa_id}_{row_filial_id}"
                if logo_key not in logo_cache:
                    logo_cache[logo_key] = get_filial_logo(db_alias, row_empresa_id, row_filial_id)
                filial_logo = logo_cache.get(logo_key)
                # set header logo to first available when printing all
                if not empresa_id and not filial_id and filial_logo and not logo_cache.get('header'):
                    logo_cache['header'] = filial_logo
        except Exception:
            filial_logo = None

        data.append({
            'titu_titu': getattr(o, 'titu_titu', '') or getattr(o, 'bapa_titu', ''),
            'titu_forn': forn,
            'fornecedor_nome': fornecedores.get(forn, ''),
            'titu_valo': valo,
            'titu_parc': parc,
            'titu_venc': venc,
            'bapa_dpag': dpag,
            'titu_aber': aber,
            'empresa_id': row_empresa_id,
            'empresa_nome': empresa_display,
            'filial_id': row_filial_id,
            'filial_nome': filial_display,
            'filial_logo': filial_logo,
        })

        # update empresa totals
        if row_empresa_id not in empresas_totals:
            empresas_totals[row_empresa_id] = {'nome': empresa_display, 'valor': 0.0, 'count': 0}
        empresas_totals[row_empresa_id]['valor'] += val_float
        empresas_totals[row_empresa_id]['count'] += 1

        # update filial totals
        filial_group = filial_totals.setdefault(row_empresa_id, {})
        if row_filial_id not in filial_group:
            filial_group[row_filial_id] = {'nome': filial_display, 'valor': 0.0, 'count': 0}
        filial_group[row_filial_id]['valor'] += val_float
        filial_group[row_filial_id]['count'] += 1

    def _sort_key(row):
        try:
            emp = int(row.get('empresa_id') or 0)
        except Exception:
            emp = 0
        try:
            fil = int(row.get('filial_id') or 0)
        except Exception:
            fil = 0
        nome = str(row.get('fornecedor_nome') or '').casefold()
        venc = str(row.get('titu_venc') or '')
        titu = str(row.get('titu_titu') or '')
        return (emp, fil, nome, venc, titu)

    data.sort(key=_sort_key)


    return {
        'empresa_nome': getattr(empresa_info, 'empr_nome', '') if empresa_info else '',
        'empresa_fantasia': getattr(empresa_info, 'empr_fant', '') if empresa_info else '',
        'filial_nome': getattr(filial_info, 'empr_nome', '') if filial_info else '',
        'filial_fantasia': getattr(filial_info, 'empr_fant', '') if filial_info else '',
        'filial_logo': get_filial_logo(db_alias, empresa_id, filial_id) if (empresa_id and filial_id) else None,
        'data': data,
        'empresas_totals': empresas_totals,
        'filial_totals': filial_totals,
        'logo_cache': logo_cache,
          'filial_logo': (logo_cache.get(f"{empresa_id}_{filial_id}") if (empresa_id and filial_id) else None),
        'header_logo': (logo_cache.get('header') if logo_cache else None),
          'total_sum': total_sum,
          'total_count': len(data),
        'period': period,
        'status': status,
        'today': today,
    }


def prepare_receber_print_data(db_alias, empresa_id, filial_id, period='hoje', status=None, vencimento_inicial=None, vencimento_final=None):
    """
    Prepare data for accounts receivable print view
    """
    from contas_a_receber.models import Titulosreceber, Baretitulos
    from Licencas.models import Empresas, Filiais
    from datetime import datetime
    
    today = _local_today()
    venc_ini = None
    venc_fim = None
    try:
        if vencimento_inicial:
            venc_ini = date.fromisoformat(str(vencimento_inicial).strip())
    except Exception:
        venc_ini = None
    try:
        if vencimento_final:
            venc_fim = date.fromisoformat(str(vencimento_final).strip())
    except Exception:
        venc_fim = None
    usar_intervalo = bool(venc_ini or venc_fim)
    
    empresa_info = Empresas.objects.using(db_alias).filter(empr_codi=empresa_id).first() if empresa_id else None
    filial_info = (
        Filiais.objects.using(db_alias).filter(empr_empr=empresa_id, empr_codi=filial_id).first()
        if (empresa_id and filial_id)
        else None
    )
    
    clientes = dict(
        Entidades.objects.using(db_alias)
        .all()
        .values_list('enti_clie', 'enti_nome')
    )
    
    # Get titles - using same pattern as list view
    if status == 'quitado':
        w_start, w_end = _week_range(today)
        d_start, d_end = _day_bounds(today)
        w_end_inclusive = w_end + timedelta(days=1)
        qs = Baretitulos.objects.using(db_alias).all()
        if empresa_id:
            qs = qs.filter(bare_empr=empresa_id)
        if filial_id:
            qs = qs.filter(bare_fili=filial_id)
        if usar_intervalo:
            if venc_ini:
                qs = qs.filter(bare_venc__gte=venc_ini)
            if venc_fim:
                qs = qs.filter(bare_venc__lte=venc_fim)
            qs = qs.order_by('bare_empr', 'bare_fili', 'bare_venc', 'bare_titu')
        else:
            if period == 'semana':
                qs = qs.filter(bare_dpag__gte=w_start, bare_dpag__lt=w_end_inclusive)
            else:
                qs = qs.filter(bare_dpag__gte=d_start, bare_dpag__lt=d_end)
            qs = qs.order_by('bare_empr', 'bare_fili', 'bare_dpag', 'bare_titu')
    else:
        qs = Titulosreceber.objects.using(db_alias).all()
        if empresa_id:
            qs = qs.filter(titu_empr=empresa_id)
        if filial_id:
            qs = qs.filter(titu_fili=filial_id)
        qs = qs.filter(
            (Q(titu_emis__isnull=True) | Q(titu_emis__gte=date(1900,1,1))),
            (Q(titu_venc__isnull=True) | Q(titu_venc__gte=date(1900,1,1))),
        )
        if usar_intervalo:
            if venc_ini:
                qs = qs.filter(titu_venc__gte=venc_ini)
            if venc_fim:
                qs = qs.filter(titu_venc__lte=venc_fim)
        else:
            if period == 'semana':
                w_start, w_end = _week_range(today)
                qs = qs.filter(titu_venc__gte=w_start, titu_venc__lt=w_end + timedelta(days=1))
            else:
                d_start, d_end = _day_bounds(today)
                qs = qs.filter(titu_venc__gte=d_start, titu_venc__lt=d_end)
        if status == 'aberto':
            qs = qs.filter(titu_aber='A')
        if status == 'quitado':
            qs = qs.filter(titu_aber='T')
        qs = qs.order_by('titu_empr', 'titu_fili', 'titu_clie', 'titu_venc', 'titu_titu')
    
    import re
    data = []
    total_sum = 0
    logo_cache = {}
    empresas_totals = {}
    filial_totals = {}
    for o in qs:
        clie = getattr(o, 'titu_clie', '') or getattr(o, 'bare_clie', '')
        valo = getattr(o, 'titu_valo', '') or getattr(o, 'bare_valo', '') or getattr(o, 'bare_valo_pago', '')
        parc = getattr(o, 'titu_parc', '') or getattr(o, 'bare_parc', '')
        venc = getattr(o, 'titu_venc', '') or getattr(o, 'bare_venc', '')
        dpag = getattr(o, 'bare_dpag', '')
        aber = 'T' if status == 'quitado' else getattr(o, 'titu_aber', '')
        row_empresa_id = getattr(o, 'titu_empr', '') or getattr(o, 'bare_empr', '')
        row_filial_id = getattr(o, 'titu_fili', '') or getattr(o, 'bare_fili', '')
        row_empresa_info = None
        row_filial_info = None
        try:
            if row_empresa_id:
                row_empresa_info = Empresas.objects.using(db_alias).filter(empr_codi=row_empresa_id).first()
            if row_filial_id and row_empresa_info:
                row_filial_info = Filiais.objects.using(db_alias).filter(empr_empr=row_empresa_id, empr_codi=row_filial_id).first()
        except Exception:
            pass
        empresa_raw = getattr(row_empresa_info, 'empr_nome', '') if row_empresa_info else ''
        m = re.search(r"\bltda\b", empresa_raw, flags=re.IGNORECASE)
        empresa_display = empresa_raw[:m.end()].strip() if m else empresa_raw
        filial_display = (getattr(row_filial_info, 'empr_fant', '') or getattr(row_filial_info, 'empr_nome', '')) if row_filial_info else ''
        
        if valo:
            try:
                total_sum += float(valo)
            except (ValueError, TypeError):
                pass
        try:
            val_float = float(valo) if valo else 0.0
        except Exception:
            val_float = 0.0
        
        filial_logo = None
        try:
            if row_empresa_id and row_filial_id:
                logo_key = f"{row_empresa_id}_{row_filial_id}"
                if logo_key not in logo_cache:
                    logo_cache[logo_key] = get_filial_logo(db_alias, row_empresa_id, row_filial_id)
                filial_logo = logo_cache.get(logo_key)
                if not empresa_id and not filial_id and filial_logo and not logo_cache.get('header'):
                    logo_cache['header'] = filial_logo
        except Exception:
            filial_logo = None
        
        data.append({
            'titu_titu': getattr(o, 'titu_titu', '') or getattr(o, 'bare_titu', ''),
            'titu_clie': clie,
            'cliente_nome': clientes.get(clie, ''),
            'titu_valo': valo,
            'titu_parc': parc,
            'titu_venc': venc,
            'bapa_dpag': dpag,
            'titu_aber': aber,
            'empresa_id': row_empresa_id,
            'empresa_nome': empresa_display,
            'filial_id': row_filial_id,
            'filial_nome': filial_display,
            'filial_fantasia': getattr(row_filial_info, 'empr_fant', '') if row_filial_info else '',
            'filial_logo': filial_logo,
        })
        
        if row_empresa_id not in empresas_totals:
            empresas_totals[row_empresa_id] = {'nome': empresa_display, 'valor': 0.0, 'count': 0}
        empresas_totals[row_empresa_id]['valor'] += val_float
        empresas_totals[row_empresa_id]['count'] += 1
        
        filial_group = filial_totals.setdefault(row_empresa_id, {})
        if row_filial_id not in filial_group:
            filial_group[row_filial_id] = {'nome': filial_display, 'valor': 0.0, 'count': 0}
        filial_group[row_filial_id]['valor'] += val_float
        filial_group[row_filial_id]['count'] += 1

    def _sort_key(row):
        try:
            emp = int(row.get('empresa_id') or 0)
        except Exception:
            emp = 0
        try:
            fil = int(row.get('filial_id') or 0)
        except Exception:
            fil = 0
        nome = str(row.get('cliente_nome') or '').casefold()
        venc = str(row.get('titu_venc') or '')
        titu = str(row.get('titu_titu') or '')
        return (emp, fil, nome, venc, titu)

    data.sort(key=_sort_key)
    
    return {
        'empresa_nome': getattr(empresa_info, 'empr_nome', '') if empresa_info else '',
        'empresa_fantasia': getattr(empresa_info, 'empr_fant', '') if empresa_info else '',
        'filial_nome': getattr(filial_info, 'empr_nome', '') if filial_info else '',
        'filial_fantasia': getattr(filial_info, 'empr_fant', '') if filial_info else '',
        'filial_logo': get_filial_logo(db_alias, empresa_id, filial_id) if (empresa_id and filial_id) else None,
        'header_logo': (logo_cache.get('header') if logo_cache else None),
        'data': data,
        'empresas_totals': empresas_totals,
        'filial_totals': filial_totals,
        'total_sum': total_sum,
        'total_count': len(data),
        'period': period,
        'status': status,
        'today': today,
    }


def _day_bounds(target_date):
    """Return start and end datetime for a day"""
    from datetime import datetime
    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date, datetime.max.time())
    return start, end


def _week_range(target_date):
    """Return start and end datetime for the week containing target_date"""
    from datetime import datetime
    start = target_date - timedelta(days=target_date.weekday())
    start = datetime.combine(start, datetime.min.time())
    end = start + timedelta(days=6)
    end = datetime.combine(end, datetime.max.time())
    return start, end


def prepare_orcamentos_print_data(db_alias, empresa_id, filial_id):
    """
    Prepare data for budgets print view
    """
    from Orcamentos.models import Orcamentos
    from Licencas.models import Empresas, Filiais
    from datetime import datetime
    
    today = datetime.now()
    
    # Get empresa and filial info
    empresa_info = Empresas.objects.using(db_alias).filter(empr_codi=empresa_id).first()
    filial_info = Filiais.objects.using(db_alias).filter(
        empr_empr=empresa_id,
        empr_codi=filial_id
    ).first()
    
    # Get budgets - using same pattern as list view (exact date match)
    qs = Orcamentos.objects.using(db_alias).defer("pedi_stat").filter(
        pedi_empr=empresa_id,
        pedi_fili=filial_id,
        pedi_data=today.date()
    ).order_by('-pedi_nume')
    
    # Prepare data
    data = []
    total_sum = 0
    for o in qs:
        valo = getattr(o, 'pedi_tota', '')
        if valo:
            try:
                total_sum += float(valo)
            except (ValueError, TypeError):
                pass
        
        data.append({
            'pedi_nume': getattr(o, 'pedi_nume', ''),
            'pedi_forn': getattr(o, 'pedi_forn', ''),
            'pedi_data': getattr(o, 'pedi_data', ''),
            'pedi_tota': valo,
            'pedi_stat_display': getattr(o, 'get_pedi_stat_display', ''),
        })
    
    return {
        'empresa_nome': getattr(empresa_info, 'empr_nome', '') if empresa_info else '',
        'empresa_fantasia': getattr(empresa_info, 'empr_fant', '') if empresa_info else '',
        'filial_nome': getattr(filial_info, 'empr_nome', '') if filial_info else '',
        'filial_fantasia': getattr(filial_info, 'empr_fant', '') if filial_info else '',
        'filial_logo': get_filial_logo(db_alias, empresa_id, filial_id),
        'data': data,
        'total_sum': total_sum,
        'total_count': len(data),
        'today': today,
    }


def prepare_pedidos_print_data(db_alias, empresa_id, filial_id):
    """
    Prepare data for orders print view
    """
    from Vendas.models import PedidoVenda
    from Licencas.models import Empresas, Filiais
    from datetime import datetime
    
    today = datetime.now()
    
    # Get empresa and filial info
    empresa_info = Empresas.objects.using(db_alias).filter(empr_codi=empresa_id).first()
    filial_info = Filiais.objects.using(db_alias).filter(
        empr_empr=empresa_id,
        empr_codi=filial_id
    ).first()
    
    # Get orders - using same pattern as list view (exact date match)
    qs = PedidoVenda.objects.using(db_alias).filter(
        pedi_empr=empresa_id,
        pedi_fili=filial_id,
        pedi_data=today.date()
    ).order_by('-pedi_nume')
    
    # Prepare data
    data = []
    total_sum = 0
    for p in qs:
        valo = getattr(p, 'pedi_tota', '')
        if valo:
            try:
                total_sum += float(valo)
            except (ValueError, TypeError):
                pass
        
        data.append({
            'pedi_nume': getattr(p, 'pedi_nume', ''),
            'pedi_clie': getattr(p, 'pedi_clie', ''),
            'pedi_data': getattr(p, 'pedi_data', ''),
            'pedi_tota': valo,
            'pedi_stat_display': getattr(p, 'get_pedi_stat_display', ''),
        })
    
    return {
        'empresa_nome': getattr(empresa_info, 'empr_nome', '') if empresa_info else '',
        'empresa_fantasia': getattr(empresa_info, 'empr_fant', '') if empresa_info else '',
        'filial_nome': getattr(filial_info, 'empr_nome', '') if filial_info else '',
        'filial_fantasia': getattr(filial_info, 'empr_fant', '') if filial_info else '',
        'filial_logo': get_filial_logo(db_alias, empresa_id, filial_id),
        'data': data,
        'total_sum': total_sum,
        'total_count': len(data),
        'today': today,
    }


def prepare_titulos_print_data(db_alias, empresa_id, filial_id, tipo=None):
    """
    Prepare data for titles print view
    """
    from contas_a_pagar.models import Titulospagar
    from contas_a_receber.models import Titulosreceber
    from Licencas.models import Empresas, Filiais
    from datetime import datetime
    
    today = datetime.now()
    d_start, d_end = _day_bounds(today.date())
    
    # Get empresa and filial info
    empresa_info = Empresas.objects.using(db_alias).filter(empr_codi=empresa_id).first()
    filial_info = Filiais.objects.using(db_alias).filter(
        empr_empr=empresa_id,
        empr_codi=filial_id
    ).first()
    
    # Get titles - using same pattern as list view (date range on titu_emis field)
    data = []
    total_count = 0
    
    if tipo == 'pagar' or not tipo:
        pagar_qs = Titulospagar.objects.using(db_alias).filter(
            titu_empr=empresa_id,
            titu_fili=filial_id,
            titu_emis__gte=d_start,
            titu_emis__lt=d_end
        ).order_by('titu_venc', 'titu_titu')
        for t in pagar_qs:
            data.append({
                'tipo': 'Pagar',
                'titu_titu': getattr(t, 'titu_titu', ''),
                'titu_parc': getattr(t, 'titu_parc', ''),
                'titu_venc': getattr(t, 'titu_venc', ''),
                'titu_aber': getattr(t, 'titu_aber', ''),
            })
            total_count += 1
    
    if tipo == 'receber' or not tipo:
        receber_qs = Titulosreceber.objects.using(db_alias).filter(
            titu_empr=empresa_id,
            titu_fili=filial_id,
            titu_emis__gte=d_start,
            titu_emis__lt=d_end
        ).order_by('titu_venc', 'titu_titu')
        for t in receber_qs:
            data.append({
                'tipo': 'Receber',
                'titu_titu': getattr(t, 'titu_titu', ''),
                'titu_parc': getattr(t, 'titu_parc', ''),
                'titu_venc': getattr(t, 'titu_venc', ''),
                'titu_aber': getattr(t, 'titu_aber', ''),
            })
            total_count += 1
    
    return {
        'empresa_nome': getattr(empresa_info, 'empr_nome', '') if empresa_info else '',
        'empresa_fantasia': getattr(empresa_info, 'empr_fant', '') if empresa_info else '',
        'filial_nome': getattr(filial_info, 'empr_nome', '') if filial_info else '',
        'filial_fantasia': getattr(filial_info, 'empr_fant', '') if filial_info else '',
        'filial_logo': get_filial_logo(db_alias, empresa_id, filial_id),
        'data': data,
        'total_count': total_count,
        'tipo': tipo,
        'today': today,
    }
