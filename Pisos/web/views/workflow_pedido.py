from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
import json
from json import JSONDecodeError

from core.utils import get_db_from_slug
from Pisos.models import Pedidospisos


class PedidoWorkflowAjaxView(View):
    CAMPOS = {
        "financeiro": ("pedi_desc_fina_work", "pedi_data_fina_work"),
        "compra": ("pedi_desc_comp_work", "pedi_data_comp_work"),
        "instalacao": ("pedi_desc_inst_work", "pedi_data_inst_work"),
        "encerramento": ("pedi_desc_ence_work", "pedi_data_ence_work"),
    }

    def post(self, request, slug, pk):
        banco = get_db_from_slug(slug)
        pedido = get_object_or_404(
            Pedidospisos.objects.using(banco),
            pk=pk,
        )

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except JSONDecodeError:
            return JsonResponse({"ok": False, "erro": "JSON inválido."}, status=400)

        etapa = (payload.get("etapa") or "").strip()
        descricao = str(payload.get("descricao", "") or "").strip()
        data_raw = str(payload.get("data") or "").strip()
        if data_raw:
            parsed = parse_date(data_raw)
            if not parsed:
                return JsonResponse({"ok": False, "erro": "Data inválida."}, status=400)
            data_work = parsed.isoformat()
        else:
            data_work = timezone.localdate().isoformat()

        if etapa not in self.CAMPOS:
            return JsonResponse({"ok": False, "erro": "Etapa inválida."}, status=400)

        campo_desc, campo_data = self.CAMPOS[etapa]

        setattr(pedido, campo_desc, descricao)
        setattr(pedido, campo_data, data_work)

        try:
            pedido.save(
                using=banco,
                update_fields=[campo_desc, campo_data],
            )
        except (ValueError, TypeError) as e:
            return JsonResponse({"ok": False, "erro": str(e)}, status=400)

        return JsonResponse({
            "ok": True,
            "etapa": etapa,
            "descricao": descricao,
            "data": data_work,
        })
