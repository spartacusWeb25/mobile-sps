from processos.models import (
    ChecklistItem,
    ChecklistModelo,
    Processo,
    ProcessoChecklistResposta,
)


class ChecklistService:
    @staticmethod
    def criar_modelo(
        *, db_alias, empresa, filial, nome, ativo=True
    ):
        return ChecklistModelo.objects.using(db_alias).create(
            chmo_empr=empresa,
            chmo_fili=filial,
            chmo_nome=nome,
            chmo_ativ=ativo,
        )

    @staticmethod
    def criar_item(
        *, db_alias, empresa, filial, modelo, descricao, obrigatorio=True
    ):
        return ChecklistItem.objects.using(db_alias).create(
            chit_empr=empresa,
            chit_fili=filial,
            chit_mode=modelo,
            chit_desc=descricao,
            chit_obri=obrigatorio,
        )

    def criar_ou_atualizar_item(
        *, db_alias, empresa, filial, modelo, descricao, obrigatorio=True
    ):
        return ChecklistItem.objects.using(db_alias).update_or_create(
            chit_empr=empresa,
            chit_fili=filial,
            chit_mode=modelo,
            chit_desc=descricao,
            defaults={
                "chit_obri": obrigatorio,
            }
        )

    @staticmethod
    def alternar_status_modelo(db_alias, empresa, filial, modelo_id):
        modelo = ChecklistModelo.objects.using(db_alias).get(
            id=modelo_id,
            chmo_empr=empresa,
            chmo_fili=filial,
        )
        modelo.chmo_ativ = not modelo.chmo_ativ
        modelo.save(using=db_alias, update_fields=["chmo_ativ"])
        return modelo.chmo_ativ

    @staticmethod
    def obter_modelo_de_processo(*, db_alias, empresa, filial, processo_id):
        return (
            ChecklistModelo.objects.using(db_alias)
            .get(
                chmo_empr=empresa,
                chmo_fili=filial,
                processo__id=processo_id
            )
        )

    @staticmethod
    def sincronizar_respostas_para_processo(*, db_alias, empresa, filial, processo):
        modelo = ChecklistService.obter_modelo_de_processo(
            db_alias=db_alias,
            empresa=empresa,
            filial=filial,
            processo_id=processo.id
        )
        if not modelo:
            return {"modelo": None, "respostas": [], "criadas": 0}

        respostas = []
        criadas = 0
        atualizadas = 0
        itens = (
            modelo.itens.using(db_alias)
            .filter(chit_empr=empresa, chit_fili=filial)
        )
        respostas_antigas = ProcessoChecklistResposta.objects.using(db_alias).filter(
            pchr_empr=empresa,
            pchr_fili=filial,
            pchr_proc=processo,
        )
        respostas_antigas.exclude(pchr_vers__isnull=False).exclude(pchr_item__in=itens).delete()
        for item in itens:
            resposta, criada = ProcessoChecklistResposta.objects.using(
                db_alias
            ).get_or_create(
                pchr_empr=empresa,
                pchr_fili=filial,
                pchr_proc=processo,
                pchr_item=item,
                pchr_vers=None,
                defaults={
                    'pchr_obri': item.chit_obri,
                    'pchr_desc': item.chit_desc,
                }
            )
            if criada:
                criadas += 1
            else:
                if resposta.pchr_obri != item.chit_obri or resposta.pchr_desc != item.chit_desc:
                    resposta.pchr_obri = item.chit_obri
                    resposta.pchr_desc = item.chit_desc
                    resposta.save(update_fields=['pchr_obri', 'pchr_desc'])
                    atualizadas += 1
        return {"modelo": modelo, "respostas": respostas, "criadas": criadas, "atualizadas": atualizadas}

    @staticmethod
    def gerar_respostas_para_processo(*, db_alias, empresa, filial, processo):
        resultado = ChecklistService.sincronizar_respostas_para_processo(
            db_alias=db_alias,
            empresa=empresa,
            filial=filial,
            processo=processo,
        )
        return resultado["respostas"]

    @staticmethod
    def _normalizar_dados_respostas(dados):
        """Aceita payload REST em dict {item_id: {...}} ou lista [{item_id, ...}]."""
        if isinstance(dados, list):
            return {
                str(item.get("item_id") or item.get("id")): {
                    "resposta": item.get("resposta"),
                    "observacao": item.get("observacao"),
                }
                for item in dados
                if item.get("item_id") or item.get("id")
            }
        return dados or {}

    @staticmethod
    def salvar_respostas(*, db_alias, empresa, filial, processo_id, dados):
        Processo.objects.using(db_alias).get(
            id=processo_id, proc_empr=empresa, proc_fili=filial
        )
        dados = ChecklistService._normalizar_dados_respostas(dados)
        respostas_salvas = []
        for resposta_id, payload in dados.items():
            resposta = ProcessoChecklistResposta.objects.using(db_alias).get(
                pchr_empr=empresa,
                pchr_fili=filial,
                pchr_proc_id=processo_id,
                id=resposta_id,
            )
            resposta.pchr_resp = payload.get("resposta")
            resposta.pchr_obse = payload.get("observacao")
            resposta.save(using=db_alias)
            respostas_salvas.append(resposta)
        return respostas_salvas
