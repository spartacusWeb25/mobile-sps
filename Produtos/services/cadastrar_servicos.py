from Produtos.models import Produtos
from django.db.models import Max
from decimal import Decimal, InvalidOperation

class ServicoService:
    def cadastrar_servico_padrao(banco, empresa_id, prod_desc, prod_unme, prod_exig_iss, prod_iss, prod_codi_serv, prod_desc_serv, prod_list_tabe_prec, prod_cnae):
        prod_e_serv = True
        ultimo_codigo = Produtos.objects.using(banco).filter(prod_empr=empresa_id).aggregate(Max('prod_codi'))['prod_codi__max']
        if not ultimo_codigo:
            ultimo_num = 0
        else:
            try:
                # tenta extrair dígitos e converter para inteiro
                digits = ''.join(ch for ch in str(ultimo_codigo) if ch.isdigit())
                ultimo_num = int(digits) if digits else 0
            except Exception:
                ultimo_num = 0

        novo_num = ultimo_num + 1
        # prefixo para serviços
        prefix = 'SER'
        novo_codigo = f"{prefix}{novo_num}"
        if not prod_desc:
            prod_desc = prod_desc_serv or ''

        prod_iss_val = None
        if prod_iss not in (None, ''):
            try:
                prod_iss_val = Decimal(str(prod_iss))
            except (InvalidOperation, ValueError):
                prod_iss_val = None

        obj_servico = Produtos.objects.using(banco).create(
            prod_empr=empresa_id,
            prod_codi=novo_codigo,
            prod_unme=prod_unme,
            prod_e_serv=prod_e_serv,
            prod_exig_iss=prod_exig_iss,
            prod_iss=prod_iss_val,
            prod_codi_serv=prod_codi_serv,
            prod_desc_serv=prod_desc_serv,
            prod_list_tabe_prec=prod_list_tabe_prec,
            prod_cnae=prod_cnae,
        )
        return obj_servico
