from django.db.models import Q
from django.http import JsonResponse

from core.utils import get_db_from_slug
from planogerencial.models import PlanoGerencialConta


def autocomplete_planocontas(request, slug=None):
    db_alias = get_db_from_slug(slug) if slug else "default"
    empresa_id = request.session.get("empresa_id")
    term = (request.GET.get("term") or request.GET.get("q") or "").strip()
    analitico = str(request.GET.get("analitico") or "").lower() in ("1", "true", "sim", "yes")

    qs = PlanoGerencialConta.objects.using(db_alias).all()
    if empresa_id:
        qs = qs.filter(gere_empr=int(empresa_id))
    if analitico:
        qs = qs.filter(gere_anal="A")
    qs = qs.filter(Q(gere_inat=False) | Q(gere_inat__isnull=True))

    if term:
        if term.isdigit():
            qs = qs.filter(Q(gere_redu=int(term)) | Q(gere_nome__icontains=term))
        else:
            qs = qs.filter(Q(gere_nome__icontains=term) | Q(gere_expa__icontains=term))

    data = [
        {
            "id": str(obj.gere_redu),
            "value": obj.gere_redu,
            "label": f"{obj.gere_redu} - {obj.gere_nome or ''}".strip(),
            "text": f"{obj.gere_redu} - {obj.gere_nome or ''}".strip(),
        }
        for obj in qs.order_by("gere_redu")[:30]
    ]
    return JsonResponse({"results": data})
