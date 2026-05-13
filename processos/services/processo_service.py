from django.db import transaction
from django.utils import timezone
from processos.models import Processo, ProcessoTipo
from .checklist_service import ChecklistService
from O_S.services.os_service import OsService


class ProcessoService:
    @staticmethod
    def listar(*, db_alias, empresa, filial):
        return (
            Processo.objects.using(db_alias)
            .filter(proc_empr=empresa, proc_fili=filial)
            .select_related("proc_tipo")
            .order_by("-id")
        )

    @staticmethod
    def listar_tipos(*, db_alias, empresa, filial):
        return ProcessoTipo.objects.using(db_alias).filter(
            prot_empr=empresa,
            prot_fili=filial,
            prot_ativ=True,
        ).order_by("prot_nome")

    @staticmethod
    def criar_tipo(*, db_alias, empresa, filial, nome, codigo, ativo=True):
        return ProcessoTipo.objects.using(db_alias).create(
            prot_empr=empresa,
            prot_fili=filial,
            prot_nome=nome,
            prot_codi=codigo,
            prot_ativ=ativo,
        )

    @staticmethod
    def criar(*, db_alias, empresa, filial, tipo_id, descricao, cliente_id=None, usuario_id=None):
        tipo = ProcessoTipo.objects.using(db_alias).get(
            id=tipo_id,
            prot_empr=empresa,
            prot_fili=filial,
            prot_ativ=True,
        )

        processo = Processo.objects.using(db_alias).create(
            proc_empr=empresa,
            proc_fili=filial,
            proc_tipo=tipo,
            proc_desc=descricao,
            proc_clie=cliente_id,
            proc_stat=Processo.STATUS_ABERTO,
            proc_data_aber=timezone.now(),
            proc_usro_aber=usuario_id,
            proc_usro_vali=usuario_id,
        )

        ChecklistService.gerar_respostas_para_processo(
            db_alias=db_alias,
            empresa=empresa,
            filial=filial,
            processo=processo,
        )

        return processo

    @staticmethod
    def mudar_status(*, db_alias, processo_id, empresa, filial, status):
        processo = Processo.objects.using(db_alias).get(
            id=processo_id,
            proc_empr=empresa,
            proc_fili=filial,
        )
        processo.proc_stat = status
        if status in [Processo.STATUS_APROVADO, Processo.STATUS_REPROVADO, Processo.STATUS_CANCELADO]:
            processo.proc_data_fech = timezone.now()
        processo.save(using=db_alias)
        return processo

    @staticmethod
    def avancar_ordem_de_servico(*, db_alias, processo_id, empresa, filial, usuario_id=None):
        with transaction.atomic(using=db_alias):
            processo = (
                Processo.objects.using(db_alias)
                .select_related("proc_tipo")
                .get(
                    id=processo_id,
                    proc_empr=empresa,
                    proc_fili=filial,
                )
            )

            if processo.proc_stat != Processo.STATUS_APROVADO:
                raise ValueError("O processo precisa estar aprovado para abrir OS.")

            if processo.proc_os:
                raise ValueError(f"Este processo já possui OS vinculada: {processo.proc_os}")

            os_data = {
                        "os_empr": empresa,
                        "os_fili": filial,
                        "os_data_aber": timezone.now().date(),
                        "os_stat_os": 1,
                        "os_desc": 0,
                        "os_tota": 0,

                        "os_clie": processo.proc_clie if processo.proc_clie else None,

                        "os_obse": f"OS gerada pelo processo #{processo.id} - {processo.proc_desc or ''}",
                        "os_usua": usuario_id,
                    }
            ordem = OsService.create_os(
                banco=db_alias,
                os_data=os_data,
                pecas_data=[],
                servicos_data=[],
                horas_data=[],
            )

            try:
                processo.proc_os = ordem.os_os
                processo.proc_os_cria_em = timezone.now()
                processo.save(
                    using=db_alias,
                    update_fields=["proc_os", "proc_os_cria_em"],
                )
            except Exception as e:
                # Rollback the transaction if OS creation fails
                transaction.set_rollback(True)
                raise e

            return ordem