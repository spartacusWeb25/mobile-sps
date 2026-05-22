# Pisos/views/status_workflow_views.py

import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from core.utils import get_db_from_slug
from Pisos.services.workflow_status_service import WorkflowStatusPisosService
from Pisos.services.status_listar import StatusPisosServices    

@require_POST
def alterar_status_pedido_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    try:
        body = json.loads(request.body)
        novo_status = int(body.get("status"))
        empresa = int(body.get("empresa"))
        filial = int(body.get("filial"))

        pedido, status = WorkflowStatusPisosService.alterar_status_pedido(
            banco=banco,
            empresa=empresa,
            filial=filial,
            numero=pk,
            novo_codigo=novo_status,
        )

        return JsonResponse({
            "ok": True,
            "status_codigo": status.stat_codigo,
            "status_desc": status.stat_desc,
            "status_cor": status.stat_cor,
        })

    except ValidationError as e:
        return JsonResponse({"ok": False, "erro": str(e)}, status=400)

    except Exception as e:
        return JsonResponse({"ok": False, "erro": str(e)}, status=500)



@require_POST
def alterar_status_orcamento_pisos(request, slug, pk):
    banco = get_db_from_slug(slug)

    try:
        body = json.loads(request.body)
        novo_status = int(body.get("status"))
        empresa = int(body.get("empresa"))
        filial = int(body.get("filial"))

        orcamento, status = WorkflowStatusPisosService.alterar_status_orcamento(
            banco=banco,
            empresa=empresa,
            filial=filial,
            numero=pk,
            novo_codigo=novo_status,
        )

        return JsonResponse({
            "ok": True,
            "status_codigo": status.stat_codigo,
            "status_desc": status.stat_desc,
            "status_cor": status.stat_cor,
        })

    except ValidationError as e:
        return JsonResponse({"ok": False, "erro": str(e)}, status=400)

    except Exception as e:
        return JsonResponse({"ok": False, "erro": str(e)}, status=500)