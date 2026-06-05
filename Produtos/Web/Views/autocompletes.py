from django.http import JsonResponse
from django.db.models import Q
from core.utils import get_licenca_db_config, get_ncm_master_db

from CFOP.models import CFOP as CFOPModel, NCM_CFOP_DIF
from ...models import (
    GrupoProduto,
    SubgrupoProduto,
    FamiliaProduto,
    Marca,
    Ncm,
    UnidadeMedida,
)



def autocomplete_unidades(request, slug=None):
    banco = get_ncm_master_db(request)
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = UnidadeMedida.objects.using(banco).all()
    if term:
        qs = qs.filter(Q(unid_codi__icontains=term) | Q(unid_desc__icontains=term))
    qs = qs.order_by('unid_desc')[:30]
    data = [{'value': obj.unid_codi, 'label': f"{obj.unid_codi} - {obj.unid_desc}"} for obj in qs]
    return JsonResponse({'results': data})

def autocomplete_grupos(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = GrupoProduto.objects.using(banco).all()
    if term:
        qs = qs.filter(Q(descricao__icontains=term) | Q(codigo__icontains=term))
    qs = qs.order_by('descricao')[:30]
    data = [{'value': obj.codigo, 'label': f"{obj.codigo} - {obj.descricao}"} for obj in qs]
    return JsonResponse({'results': data})

def autocomplete_subgrupos(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = SubgrupoProduto.objects.using(banco).all()
    if term:
        qs = qs.filter(Q(descricao__icontains=term) | Q(codigo__icontains=term))
    qs = qs.order_by('descricao')[:30]
    data = [{'value': obj.codigo, 'label': f"{obj.codigo} - {obj.descricao}"} for obj in qs]
    return JsonResponse({'results': data})


def autocomplete_familias(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = FamiliaProduto.objects.using(banco).all()
    if term:
        qs = qs.filter(Q(descricao__icontains=term) | Q(codigo__icontains=term))
    qs = qs.order_by('descricao')[:30]
    data = [{'value': obj.codigo, 'label': f"{obj.codigo} - {obj.descricao}"} for obj in qs]
    return JsonResponse({'results': data})

def autocomplete_marcas(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = Marca.objects.using(banco).all()
    if term:
        qs = qs.filter(Q(nome__icontains=term) | Q(codigo__icontains=term))
    qs = qs.order_by('nome')[:30]
    data = [{'value': obj.codigo, 'label': f"{obj.codigo} - {obj.nome}"} for obj in qs]
    return JsonResponse({'results': data})


def autocomplete_ncms(request, slug=None):
    banco = get_ncm_master_db(request)
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = Ncm.objects.using(banco).all()
    if term:
        digits = ''.join(ch for ch in term if ch.isdigit())
        dotted = None
        if digits and len(digits) == 8:
            dotted = f"{digits[:4]}.{digits[4:6]}.{digits[6:]}"
        q = Q(ncm_codi__icontains=term) | Q(ncm_desc__icontains=term)
        if dotted:
            q = q | Q(ncm_codi__icontains=dotted)
        if digits and digits != term:
            q = q | Q(ncm_codi__icontains=digits)
        qs = qs.filter(q)
    qs = qs.order_by('ncm_codi')[:30]
    data = [{'value': obj.ncm_codi, 'label': f"{obj.ncm_codi} - {obj.ncm_desc}"} for obj in qs]
    return JsonResponse({'results': data})


def autocomplete_servicos(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    empresa_id = request.session.get('empresa_id')
    
    from Produtos.models import Produtos
    
    qs = Produtos.objects.using(banco).filter(prod_e_serv=True)
    
    if empresa_id:
        qs = qs.filter(prod_empr=str(empresa_id))
    
    if term:
        qs = qs.filter(
            Q(prod_desc_serv__icontains=term) |
            Q(prod_codi__icontains=term) |
            Q(prod_codi_serv__icontains=term)
        )
    
    qs = qs.order_by('prod_codi')[:30]
    
    data = []
    for servico in qs:
        data.append({
            'value': servico.prod_codi,
            'label': f"{servico.prod_codi} - {servico.prod_desc_serv or ''}",
        })
    
    return JsonResponse({'results': data})


def ncm_fiscal_padrao(request, slug=None):
    banco_tenant = get_licenca_db_config(request) or "default"
    banco = get_ncm_master_db(banco_tenant)
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = Ncm.objects.using(banco).all()
    if term:
        digits = ''.join(ch for ch in term if ch.isdigit())
        dotted = None
        if digits and len(digits) == 8:
            dotted = f"{digits[:4]}.{digits[4:6]}.{digits[6:]}"
        q = Q(ncm_codi__icontains=term) | Q(ncm_desc__icontains=term)
        if dotted:
            q = q | Q(ncm_codi__icontains=dotted)
        if digits and digits != term:
            q = q | Q(ncm_codi__icontains=digits)
        qs = qs.filter(q)
    qs = qs.order_by('ncm_codi')[:30]
    data = [{'value': obj.ncm_codi, 'label': f"{obj.ncm_codi} - {obj.ncm_desc}"} for obj in qs]
    return JsonResponse({'results': data})


def autocomplete_cnaes(request, slug=None):
    import json, os, re
    term = (request.GET.get('term') or request.GET.get('q') or '').strip().lower()
    here = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.normpath(os.path.join(here, '..', '..', 'data', 'servicos_cnaes.json'))
    choices = []
    # 1) Tenta ler do arquivo local
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
            choices = payload.get('cnaes', [])
    except Exception:
        choices = []

    # 2) Se não encontrou no arquivo, tenta buscar no site oficial e atualiza o arquivo
    if not choices:
        try:
            import requests
            GOV_URL = 'https://www.gov.br/nfse/pt-br/mei-e-demais-empresas/codigos-de-tributacao-nacional-nbs'
            resp = requests.get(GOV_URL, timeout=10)
            text = resp.text if resp.status_code == 200 else ''
            matches = re.findall(r"(\d{6})\s*-\s*([^<\n\r]+)", text)
            for m in matches:
                codigo = m[0].strip()
                desc = m[1].strip()
                choices.append({'value': codigo, 'label': f"{codigo} - {desc}"})
            # gravar cache local (silencioso)
            try:
                os.makedirs(os.path.dirname(data_path), exist_ok=True)
                if os.path.exists(data_path):
                    with open(data_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                else:
                    existing = {}
                existing['cnaes'] = choices
                with open(data_path, 'w', encoding='utf-8') as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        except Exception:
            # fallback para consulta ao master NCM
            try:
                banco = get_ncm_master_db(request)
                qs = Ncm.objects.using(banco).all()
                qs = qs.order_by('ncm_codi')[:300]
                choices = [{'value': obj.ncm_codi, 'label': f"{obj.ncm_codi} - {obj.ncm_desc}"} for obj in qs]
            except Exception:
                choices = []

    # filtra por termo
    if term:
        filtered = [c for c in choices if term in c.get('label','').lower() or term in c.get('value','').lower()]
    else:
        filtered = choices[:300]
    return JsonResponse({'results': filtered})


def ncm_fiscal_padrao(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    empresa_id = request.session.get('empresa_id') or request.headers.get('X-Empresa') or request.GET.get('empresa')
    ncm_code = (request.GET.get('ncm') or '').strip()
    cfop_code = (request.GET.get('cfop') or '').strip()
    resp = {'ncm': ncm_code, 'empresa': empresa_id, 'aliquotas': {}, 'override': {}}
    if not ncm_code:
        return JsonResponse(resp)
    ncm_db = get_ncm_master_db(banco)
    raw = str(ncm_code).strip()
    digits = ''.join(ch for ch in raw if ch.isdigit())
    candidates = []
    for c in (raw, digits):
        c = (c or '').strip()
        if c and c not in candidates:
            candidates.append(c)
    if digits and len(digits) == 8:
        dotted = f"{digits[:4]}.{digits[4:6]}.{digits[6:]}"
        if dotted not in candidates:
            candidates.insert(1, dotted)
    ncm = None
    for code in candidates:
        ncm = Ncm.objects.using(ncm_db).filter(ncm_codi=code).first()
        if ncm:
            break
    if not ncm and digits:
        from django.db.models import F, Value
        from django.db.models.functions import Replace
        ncm = (
            Ncm.objects.using(ncm_db)
            .annotate(
                _ncm_norm=Replace(
                    Replace(F("ncm_codi"), Value("."), Value("")),
                    Value(" "),
                    Value(""),
                )
            )
            .filter(_ncm_norm=digits)
            .first()
        )
    if ncm:
        from Produtos.models import NcmFiscalPadrao as NcmFiscalPadraoModel
        qs = NcmFiscalPadraoModel.objects.using(banco).filter(nfiscalpadrao_ncm=ncm)
        if empresa_id:
            try:
                qs = qs.filter(nfiscalpadrao_empr=int(empresa_id))
            except Exception:
                qs = qs.filter(nfiscalpadrao_empr=empresa_id)
        aliq = qs.first()
        if aliq:
            resp['aliquotas'] = {
                'ipi': aliq.nfiscalpadrao_aliq_ipi,
                'pis': aliq.nfiscalpadrao_aliq_pis,
                'cofins': aliq.nfiscalpadrao_aliq_cofins,
                'cbs': aliq.nfiscalpadrao_aliq_cbs,
                'ibs': aliq.nfiscalpadrao_aliq_ibs,
            }
    if ncm and cfop_code:
        cfop = CFOPModel.objects.using(banco).filter(cfop_codi=cfop_code).first()
        if cfop and empresa_id:
            override = NCM_CFOP_DIF.objects.using(banco).filter(ncm=ncm, cfop=cfop, ncm_empr=int(empresa_id)).first()
            if override:
                resp['override'] = {
                    'ipi': override.ncm_ipi_dif,
                    'pis': override.ncm_pis_dif,
                    'cofins': override.ncm_cofins_dif,
                    'cbs': override.ncm_cbs_dif,
                    'ibs': override.ncm_ibs_dif,
                    'icms': override.ncm_icms_aliq_dif,
                    'st': override.ncm_st_aliq_dif,
                }
    return JsonResponse(resp)
