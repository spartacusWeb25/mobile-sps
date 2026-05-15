import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.utils import get_licenca_db_config
from Produtos.models import GrupoProduto, SubgrupoProduto, FamiliaProduto, Marca


def _read_payload(request):
    if request.content_type and "application/json" in request.content_type.lower():
        try:
            return json.loads(request.body.decode("utf-8") or "{}") or {}
        except Exception:
            return {}
    return request.POST.dict()


def _next_numeric_code(qs, field_name):
    max_num = 0
    for row in qs.values_list(field_name, flat=True):
        raw = str(row or "").strip()
        if not raw.isdigit():
            continue
        try:
            max_num = max(max_num, int(raw))
        except Exception:
            continue
    return str(max_num + 1)


@require_POST
def ajax_create_grupo(request, slug=None):
    banco = get_licenca_db_config(request) or "default"
    data = _read_payload(request)
    codigo = str(data.get("codigo") or "").strip()
    descricao = str(data.get("descricao") or data.get("nome") or "").strip()
    if not descricao:
        return JsonResponse({"detail": "Descrição é obrigatória."}, status=400)

    if not codigo:
        codigo = _next_numeric_code(GrupoProduto.objects.using(banco).all(), "codigo")

    obj = GrupoProduto(codigo=codigo, descricao=descricao)
    obj.save(using=banco)
    return JsonResponse({"value": obj.codigo, "label": f"{obj.codigo} - {obj.descricao}"})


@require_POST
def ajax_create_subgrupo(request, slug=None):
    banco = get_licenca_db_config(request) or "default"
    data = _read_payload(request)
    codigo = str(data.get("codigo") or "").strip()
    descricao = str(data.get("descricao") or data.get("nome") or "").strip()
    if not descricao:
        return JsonResponse({"detail": "Descrição é obrigatória."}, status=400)

    if not codigo:
        codigo = _next_numeric_code(SubgrupoProduto.objects.using(banco).all(), "codigo")

    obj = SubgrupoProduto(codigo=codigo, descricao=descricao)
    obj.save(using=banco)
    return JsonResponse({"value": obj.codigo, "label": f"{obj.codigo} - {obj.descricao}"})


@require_POST
def ajax_create_familia(request, slug=None):
    banco = get_licenca_db_config(request) or "default"
    data = _read_payload(request)
    codigo = str(data.get("codigo") or "").strip()
    descricao = str(data.get("descricao") or data.get("nome") or "").strip()
    if not descricao:
        return JsonResponse({"detail": "Descrição é obrigatória."}, status=400)

    if not codigo:
        codigo = _next_numeric_code(FamiliaProduto.objects.using(banco).all(), "codigo")

    obj = FamiliaProduto(codigo=codigo, descricao=descricao)
    obj.save(using=banco)
    return JsonResponse({"value": obj.codigo, "label": f"{obj.codigo} - {obj.descricao}"})


@require_POST
def ajax_create_marca(request, slug=None):
    banco = get_licenca_db_config(request) or "default"
    data = _read_payload(request)
    nome = str(data.get("nome") or data.get("descricao") or "").strip()
    if not nome:
        return JsonResponse({"detail": "Nome é obrigatório."}, status=400)

    obj = Marca(nome=nome)
    obj.save(using=banco)
    return JsonResponse({"value": obj.codigo, "label": f"{obj.codigo} - {obj.nome}"})

