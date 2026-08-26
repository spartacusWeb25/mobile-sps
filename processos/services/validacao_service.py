from django.utils import timezone

from distutils import version
from processos.models import Processo, ProcessoChecklistResposta
from Entidades.models import Entidades

import logging
logger = logging.getLogger("__name__")

class ValidacaoProcessoService:
    @staticmethod
    def validar_assinatura(*, db_alias, empresa, responsavel_id, documento_inserido):
        responsavel = Entidades.objects.using(db_alias).get(
            enti_empr = empresa,
            enti_clie = responsavel_id
        )

        if documento_inserido == responsavel.enti_cpf:
            return True
        else:
            return False

    @staticmethod
    def validar_processo(*, db_alias, empresa, filial, processo_id, usuario_id=None, responsavel_id=None, dados={}):
        processo = Processo.objects.using(db_alias).get(
            id=processo_id,
            proc_empr=empresa,
            proc_fili=filial,
        )
        respostas_proc = list(
            ProcessoChecklistResposta.objects.using(db_alias)
            .filter(
                pchr_proc=processo,
                pchr_empr=empresa,
                pchr_fili=filial,
            )
        )
        erros = []
        respostas_modificadas = []
        if dados["temp_resp"]:
            vers = processo.proc_vers
            for resposta in respostas_proc:
                if resposta.pchr_vers < vers:
                    continue
                nova_resposta = ProcessoChecklistResposta(
                        pchr_proc=processo,
                        pchr_empr=empresa,
                        pchr_fili=filial,
                        pchr_obri=resposta.pchr_obri,
                        pchr_desc=resposta.pchr_desc,
                        pchr_item=resposta.pchr_item,
                    )
                resposta_id = str(resposta.id)
                if resposta_id in dados:
                    nova_resposta.pchr_resp = dados[resposta_id]["resposta"]
                    nova_resposta.pchr_obse = dados[resposta_id]["observacao"]
                respostas_modificadas.append(nova_resposta)
                valor_resposta = nova_resposta.pchr_resp
                if nova_resposta.pchr_obri and not valor_resposta:
                    erros.append(f"Item obrigatório sem resposta: {nova_resposta.pchr_desc}")
                if nova_resposta.pchr_obri and valor_resposta == ProcessoChecklistResposta.RESP_NAO:
                    erros.append(f"Item obrigatório marcado como NÃO: {nova_resposta.pchr_desc}")
        else:
            for resposta in respostas_proc:
                if resposta.pchr_vers:
                    continue
                resposta_id = str(resposta.id)
                if resposta_id in dados:
                    resposta.pchr_resp = dados[resposta_id]["resposta"]
                    resposta.pchr_obse = dados[resposta_id]["observacao"]
                    respostas_modificadas.append(resposta)
                valor_resposta = resposta.pchr_resp
                if resposta.pchr_obri and not valor_resposta:
                    erros.append(f"Item obrigatório sem resposta: {resposta.pchr_desc}")
                if resposta.pchr_obri and valor_resposta == ProcessoChecklistResposta.RESP_NAO:
                    erros.append(f"Item obrigatório marcado como NÃO: {resposta.pchr_desc}")
        if processo.proc_vers:
            vers = processo.proc_vers+1
        else:
            vers = 1
        if erros:
            aprovado = False
            processo.proc_stat = Processo.STATUS_REPROVADO
        else:
            aprovado = True
            processo.proc_stat = Processo.STATUS_APROVADO
        processo.proc_usro_vali = usuario_id
        processo.proc_enti_vali = responsavel_id
        processo.proc_data_fech = timezone.now()
        processo.proc_vers = vers
        processo.save(using=db_alias)
        for resposta in respostas_modificadas:
            resposta.pchr_vali=aprovado
            resposta.pchr_data_vali=timezone.now()
            resposta.pchr_usro_vali=usuario_id
            resposta.pchr_enti_vali=responsavel_id
            resposta.pchr_vers=version
        if dados["temp_resp"]:
            ProcessoChecklistResposta.objects.using(db_alias).bulk_create(respostas_modificadas)
        else:
            ProcessoChecklistResposta.objects.using(db_alias).bulk_update(
                respostas_modificadas, 
                fields=["pchr_resp","pchr_obse","pchr_vali","pchr_data_vali", "pchr_usro_vali", "pchr_enti_vali", "pchr_vers"]
            )
        return {"aprovado": aprovado, "status": processo.proc_stat, "erros": erros}
        
        
        
