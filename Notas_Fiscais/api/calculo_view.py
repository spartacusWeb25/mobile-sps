from django.http import JsonResponse
from django.views.decorators.http import require_POST
from ..services.calculo_impostos_service import CalculoImpostosService
from ..models import Nota
from ..services.nota_service import NotaService
from core.utils import get_db_from_slug
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(['POST'])
def calcular_impostos(request, slug, nota_id):
    try:
        db = get_db_from_slug(slug)
        qs_debug = Nota.objects.using(db).filter(pk=nota_id)
        # #region debug-point C:calculo-candidates
        import json, urllib.request; urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId":"nota-calc-duplicate","runId":"pre-fix","hypothesisId":"C","location":"Notas_Fiscais/api/calculo_view.py:calcular_impostos","msg":"[DEBUG] calcular_impostos candidates before get","data":{"slug":str(slug or ""),"db":str(db or ""),"nota_id":str(nota_id or ""),"count":int(qs_debug.count()),"ids":[str(v) for v in qs_debug.values_list("id", flat=True)[:10]],"empresa":[str(v) for v in qs_debug.values_list("empresa", flat=True)[:10]],"filial":[str(v) for v in qs_debug.values_list("filial", flat=True)[:10]],"status":[str(v) for v in qs_debug.values_list("status", flat=True)[:10]]}}).encode(), headers={"Content-Type":"application/json"}), timeout=0.5).read()
        # #endregion
        nota = Nota.objects.using(db).get(pk=nota_id)
        
        service = CalculoImpostosService(db)

        debug_data = service.aplicar_impostos(nota, return_debug=True)
        
        totais = NotaService.atualizar_totais(nota)
        # #region debug-point D:calculo-result
        import json, urllib.request; urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId":"nota-calc-duplicate","runId":"pre-fix","hypothesisId":"D","location":"Notas_Fiscais/api/calculo_view.py:calcular_impostos","msg":"[DEBUG] calcular_impostos completed apply_impostos","data":{"nota_id":str(getattr(nota, "id", "")),"empresa":str(getattr(nota, "empresa", "")),"filial":str(getattr(nota, "filial", "")),"debug_items":len((debug_data or {}).get("itens", [])) if isinstance(debug_data, dict) else 0}}).encode(), headers={"Content-Type":"application/json"}), timeout=0.5).read()
        # #endregion
        
        return JsonResponse({
            "mensagem": "Cálculo realizado com sucesso",
            "totais": {
                "produtos": str((totais or {}).get("produtos") or "0.00"),
                "tributos": str((totais or {}).get("tributos") or "0.00"),
                "frete": str((totais or {}).get("frete") or "0.00"),
                "seguro": str((totais or {}).get("seguro") or "0.00"),
                "outras_despesas": str((totais or {}).get("outras_despesas") or "0.00"),
                "total": str((totais or {}).get("total") or "0.00"),
            },
            "debug_calculo": debug_data,
        })
    except Exception as e:
        # #region debug-point D:calculo-error
        import json, urllib.request; urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId":"nota-calc-duplicate","runId":"pre-fix","hypothesisId":"D","location":"Notas_Fiscais/api/calculo_view.py:calcular_impostos:except","msg":"[DEBUG] calcular_impostos raised exception","data":{"slug":str(slug or ""),"nota_id":str(nota_id or ""),"erro":str(e)}}).encode(), headers={"Content-Type":"application/json"}), timeout=0.5).read()
        # #endregion
        return JsonResponse({"erro": str(e)}, status=400)
