from processos.models import (
    ChecklistItem,
    ChecklistModelo,
    Processo,
    ProcessoChecklistResposta,
)


class ChecklistService:
    @staticmethod
    def criar_modelo(
        *, db_alias, empresa, filial, processo_tipo, nome, versao=1, ativo=True
    ):
        return ChecklistModelo.objects.using(db_alias).create(
            chmo_empr=empresa,
            chmo_fili=filial,
            chmo_proc_tipo=processo_tipo,
            chmo_nome=nome,
            chmo_vers=versao,
            chmo_ativ=ativo,
        )

    @staticmethod
    def criar_item(
        *, db_alias, empresa, filial, modelo, descricao, ordem=0, obrigatorio=True
    ):
        return ChecklistItem.objects.using(db_alias).create(
            chit_empr=empresa,
            chit_fili=filial,
            chit_mode=modelo,
            chit_orde=ordem,
            chit_desc=descricao,
            chit_obri=obrigatorio,
        )

    @staticmethod
    def obter_modelo_ativo(*, db_alias, empresa, filial, proc_tipo):
        return (
            ChecklistModelo.objects.using(db_alias)
            .filter(
                chmo_empr=empresa,
                chmo_fili=filial,
                chmo_proc_tipo=proc_tipo,
                chmo_ativ=True,
            )
            .order_by("-chmo_vers")
            .first()
        )

    @staticmethod
    def gerar_respostas_para_processo(*, db_alias, empresa, filial, processo):
        modelo = ChecklistService.obter_modelo_ativo(
            db_alias=db_alias,
            empresa=empresa,
            filial=filial,
            proc_tipo=processo.proc_tipo,
        )
        if not modelo:
            return []

        respostas = []
        itens = (
            modelo.itens.using(db_alias)
            .filter(chit_empr=empresa, chit_fili=filial)
            .order_by("chit_orde")
        )
        for item in itens:
            resposta, _ = ProcessoChecklistResposta.objects.using(
                db_alias
            ).get_or_create(
                pchr_empr=empresa,
                pchr_fili=filial,
                pchr_proc=processo,
                pchr_item=item,
            )
            respostas.append(resposta)
        return respostas

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
        for item_id, payload in dados.items():
            resposta = ProcessoChecklistResposta.objects.using(db_alias).get(
                pchr_empr=empresa,
                pchr_fili=filial,
                pchr_proc_id=processo_id,
                pchr_item_id=item_id,
            )
            resposta.pchr_resp = payload.get("resposta")
            resposta.pchr_obse = payload.get("observacao")
            resposta.save(using=db_alias)
            respostas_salvas.append(resposta)
        return respostas_salvas
