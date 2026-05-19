from Produtos.models import Produtos
from django.db.models import Max

class ServicoService:
    def cadastrar_servico_padrao(banco, empresa_id, prod_desc, prod_unme, prod_exig_iss, prod_iss, prod_codi_serv, prod_desc_serv, prod_list_tabe_prec, prod_cnae):
        prod_e_serv = True
        ultimo_codigo = Produtos.objects.using(banco).filter(prod_empr=empresa_id).aggregate(Max('prod_codi'))['prod_codi__max']
        if ultimo_codigo is None:
            ultimo_codigo = 0

        novo_codigo = Produtos.objects.using(banco).create(
            prod_empr=empresa_id,
            prod_codi=ultimo_codigo + 1,
            prod_desc=prod_desc,
            prod_unme=prod_unme,
            prod_e_serv=prod_e_serv,
            prod_exig_iss=prod_exig_iss,
            prod_iss=prod_iss,
            prod_codi_serv=prod_codi_serv,
            prod_desc_serv=prod_desc_serv,
            prod_list_tabe_prec=prod_list_tabe_prec,
            prod_cnae=prod_cnae,
        )
        return novo_codigo
