from django.http import JsonResponse
from django.db.models import Q
from core.utils import get_licenca_db_config
from CentrodeCustos.models import Centrodecustos
from Entidades.models import Entidades
from planogerencial.models import PlanoGerencialConta
from planocontas.models import Planodecontas
from core.utils import get_db_from_slug


def autocomplete_cc(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = Centrodecustos.objects.using(banco).filter(cecu_anal='A')
    if term:
        qs = qs.filter(Q(cecu_redu__icontains=term) | Q(cecu_nome__icontains=term))
    qs = qs.order_by('cecu_redu')[:30]
    data = [{'value': obj.cecu_redu, 'label': f"{obj.cecu_redu} - {obj.cecu_nome}"} for obj in qs]
    return JsonResponse({'results': data})


def autocomplete_bancos(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    empresa_id = (
        request.session.get('empresa_id')
        or request.headers.get('X-Empresa')
        or request.GET.get('empresa')
        or request.GET.get('empr')
    )
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()

    try:
        empresa_id = int(empresa_id)
    except (TypeError, ValueError):
        return JsonResponse({'results': []})

    qs = Entidades.objects.using(banco).filter(
        enti_empr=empresa_id,
        enti_tien__in=['B', 'C'],
        enti_tipo_enti__isnull=False,
    )

    if term:
        if term.isdigit():
            qs = qs.filter(enti_clie__icontains=term)
        else:
            qs = qs.filter(Q(enti_nome__icontains=term) | Q(enti_fant__icontains=term))

    qs = qs.order_by('enti_nome')[:20]
    data = [
        {
            'id': str(obj.enti_clie),
            'text': f"{obj.enti_clie} - {obj.enti_nome}",
        }
        for obj in qs
    ]
    return JsonResponse({'results': data})


def autocomplete_planocontas(request, slug=None):
    banco = get_db_from_slug(slug) if slug else (get_licenca_db_config(request) or 'default')
    empresa_id = request.session.get('empresa_id')
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    analitico = str(request.GET.get("analitico") or "").lower() in ("1", "true", "sim", "yes")

    qs = PlanoGerencialConta.objects.using(banco).all()
    if empresa_id:
        qs = qs.filter(gere_empr=int(empresa_id))
    if analitico:
        qs = qs.filter(gere_anal='A')
    qs = qs.filter(Q(gere_inat=False) | Q(gere_inat__isnull=True))

    if term:
        if term.isdigit():
            qs = qs.filter(Q(gere_redu=int(term)) | Q(gere_nome__icontains=term))
        else:
            qs = qs.filter(Q(gere_nome__icontains=term) | Q(gere_expa__icontains=term))

    data = [
        {'id': str(obj.gere_redu), 'text': f"{obj.gere_redu} - {obj.gere_nome or ''}".strip()}
        for obj in qs.order_by('gere_redu')[:30]
    ]
    return JsonResponse({'results': data})


def autocomplete_planodecontas(request, slug=None):
    banco = get_db_from_slug(slug) if slug else (get_licenca_db_config(request) or 'default')
    empresa_id = request.session.get('empresa_id')
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    analitico = str(request.GET.get("analitico") or "").lower() in ("1", "true", "sim", "yes")

    qs = Planodecontas.objects.using(banco).all()
    if empresa_id:
        qs = qs.filter(plan_empr=int(empresa_id))
    if analitico:
        qs = qs.filter(plan_anal='A')
    qs = qs.filter(Q(plan_inat=False) | Q(plan_inat__isnull=True))

    if term:
        if term.isdigit():
            qs = qs.filter(Q(plan_redu=int(term)) | Q(plan_nome__icontains=term))
        else:
            qs = qs.filter(Q(plan_nome__icontains=term) | Q(plan_expa__icontains=term))

    data = [
        {'id': str(obj.plan_redu), 'text': f"{obj.plan_redu} - {obj.plan_nome or ''}".strip()}
        for obj in qs.order_by('plan_redu')[:30]
    ]
    return JsonResponse({'results': data})
