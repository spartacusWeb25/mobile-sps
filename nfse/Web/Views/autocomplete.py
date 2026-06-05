from django.http import JsonResponse
from django.db.models import Q
import logging

from core.utils import get_licenca_db_config
from Entidades.models import Entidades
from Produtos.models import Produtos

logger = logging.getLogger(__name__)


def entidades_autocomplete(request, slug=None):
    """
    Endpoint: /web/<slug>/notas-de-servico/entidades-autocomplete/?q=<query>
    
    Retorna lista de entidades/clientes para autocomplete.
    """
    try:
        banco = get_licenca_db_config(request) or "default"
        empresa = request.session.get("empresa_id")
        q = (request.GET.get("q") or "").strip()

        if not empresa:
            logger.warning("Autocomplete: empresa_id não encontrado na sessão")
            return JsonResponse([], safe=False)

        qs = Entidades.objects.using(banco).filter(enti_empr=empresa)
        
        if q:
            qs = qs.filter(
                Q(enti_nome__iregex=q) | 
                Q(enti_cnpj__icontains=q) | 
                Q(enti_cpf__icontains=q)
            )

        qs = qs.order_by("enti_nome")[:20]
        
        data = []
        for e in qs:
            entity_data = {
                "value": str(e.enti_clie),
                "label": f"{e.enti_nome} • {(e.enti_cnpj or e.enti_cpf or '')}",
                "enti_clie": e.enti_clie,
                "enti_nome": e.enti_nome,
                "enti_cnpj": e.enti_cnpj or '',
                "enti_cpf": e.enti_cpf or '',
                "enti_ende": e.enti_ende or '',
                "enti_nume": e.enti_nume or '',
                "enti_bair": e.enti_bair or '',
                "enti_cepe": e.enti_cep or '',  
                "enti_cida": e.enti_cida or '',
                "enti_esta": e.enti_esta or '',
                "enti_ie": e.enti_insc_esta or '',
                "enti_fone": e.enti_fone or '',
                "enti_email": e.enti_emai or '', 
            }
            logger.debug(f"Autocomplete data for {e.enti_nome}: {entity_data}")
            data.append(entity_data)
        
        return JsonResponse(data, safe=False)
    
    except Exception as exc:
        logger.error(f"Erro em entidades_autocomplete: {exc}", exc_info=True)
        return JsonResponse({"error": str(exc)}, status=500)


def servicos_autocomplete(request, slug=None):
    """
    Endpoint: /web/<slug>/notas-de-servico/servicos-autocomplete/?q=<query>
    
    Retorna lista de serviços para autocomplete.
    """
    try:
        banco = get_licenca_db_config(request) or "default"
        empresa = request.session.get("empresa_id")
        q = (request.GET.get("q") or "").strip()

        if not empresa:
            logger.warning("Autocomplete servicos: empresa_id não encontrado na sessão")
            return JsonResponse([], safe=False)

        qs = Produtos.objects.using(banco).filter(
            prod_e_serv=True,
            prod_empr=str(empresa)
        )
        
        if q:
            qs = qs.filter(
                Q(prod_desc_serv__icontains=q) |
                Q(prod_codi__icontains=q) |
                Q(prod_codi_serv__icontains=q)
            )

        qs = qs.order_by("prod_codi")[:20]
        
        data = []
        for servico in qs:
            service_data = {
                "value": servico.prod_codi,
                "label": f"{servico.prod_codi} - {servico.prod_desc_serv or ''}",
                "codigo_servico": servico.prod_codi_serv or '',
                "descricao_servico": servico.prod_desc_serv or '',
                "cnae": servico.prod_cnae or '',
                "iss_aliquota": float(servico.prod_iss) if servico.prod_iss else 0,
                "iss_exigivel": servico.prod_exig_iss if hasattr(servico, 'prod_exig_iss') else 1,
                "unidade": str(servico.prod_unme) if servico.prod_unme else '',
            }
            logger.debug(f"Servico autocomplete: {service_data}")
            data.append(service_data)
        
        return JsonResponse(data, safe=False)
    
    except Exception as exc:
        logger.error(f"Erro em servicos_autocomplete: {exc}", exc_info=True)
        return JsonResponse({"error": str(exc)}, status=500)