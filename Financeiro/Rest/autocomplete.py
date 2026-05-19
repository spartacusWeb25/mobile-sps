from django.db.models import Q
from django.http import JsonResponse
from CentrodeCustos.models import Centrodecustos
from core.utils import get_licenca_db_config
from Entidades.models import Entidades
from planogerencial.models import PlanoGerencialConta
from planocontas.models import Planodecontas
from core.utils import get_db_from_slug


def autocomplete_cc(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    empresa_id = request.session.get("empresa_id")
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = Centrodecustos.objects.using(banco).filter(cecu_anal='A')
    if empresa_id:
        qs = qs.filter(cecu_empr=int(empresa_id))
    if term:
        qs = qs.filter(Q(cecu_redu__icontains=term) | Q(cecu_nome__icontains=term))
    qs = qs.order_by('cecu_redu')[:30]
    data = [{'value': obj.cecu_redu, 'label': f"{obj.cecu_redu} - {obj.cecu_nome}"} for obj in qs]
    return JsonResponse({'results': data})


def autocomplete_bancos_caixas(request, slug=None):
    banco = get_licenca_db_config(request) or 'default'
    empresa_id = request.session.get("empresa_id")
    term = (request.GET.get('term') or request.GET.get('q') or '').strip()
    qs = Entidades.objects.using(banco).filter(enti_tien__in=['B', 'C'])
    if empresa_id:
        qs = qs.filter(enti_empr=int(empresa_id))
    if term:
        if term.isdigit():
            qs = qs.filter(Q(enti_clie=int(term)) | Q(enti_nome__icontains=term))
        else:
            qs = qs.filter(Q(enti_nome__icontains=term))
    qs = qs.order_by('enti_nome')[:30]
    data = [{'value': obj.enti_clie, 'label': f"{obj.enti_clie} - {obj.enti_nome}"} for obj in qs]
    return JsonResponse({'results': data})


def autocomplete_planocontas(request, slug=None):
    banco = get_db_from_slug(slug) if slug else (get_licenca_db_config(request) or 'default')
    empresa_id = request.session.get("empresa_id")
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

    data = [{'value': obj.gere_redu, 'label': f"{obj.gere_redu} - {obj.gere_nome or ''}".strip()} for obj in qs.order_by('gere_redu')[:30]]
    return JsonResponse({'results': data})


def autocomplete_planocontas_normal(request, slug=None):
    banco = get_db_from_slug(slug) if slug else (get_licenca_db_config(request) or 'default')
    empresa_id = request.session.get("empresa_id")
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

    data = [{'value': obj.plan_redu, 'label': f"{obj.plan_redu} - {obj.plan_nome or ''}".strip()} for obj in qs.order_by('plan_redu')[:30]]
    return JsonResponse({'results': data})
