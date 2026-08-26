from django.db.models import Subquery, OuterRef
from django.utils import timezone
from processos.models import Processo, ChecklistModelo
from .checklist_service import ChecklistService
from O_S.models import Os
from Entidades.models import Entidades

class ProcessoService:
    @staticmethod
    def listar(*, db_alias, empresa, filial):
        return (
            Processo.objects.using(db_alias)
            .filter(proc_empr=empresa, proc_fili=filial)
            .select_related("proc_mode")
            .order_by("-id")
        )

    @staticmethod
    def listar_modelos(*, db_alias, empresa, filial, ativo=True):
        return ChecklistModelo.objects.using(db_alias).filter(
            chmo_empr=empresa,
            chmo_fili=filial,
            chmo_ativ=ativo,
        )

    @staticmethod
    def listar_os_sem_processo(*, db_alias, empresa, filial):
        cliente_nome_subquery = Entidades.objects.filter(
            enti_empr=OuterRef('os_empr'),
            enti_clie=OuterRef('os_clie')
        ).values('enti_nome')[:1]

        return Os.objects.using(db_alias).filter(
            os_empr=empresa,
            os_fili=filial,
            processo__isnull=True
        ).annotate(
            clie_nome=Subquery(cliente_nome_subquery)
        ).order_by("-os_os")

    @staticmethod
    def criar(*, db_alias, empresa, filial, modelo_id, descricao=None, usuario_id=None, os=None):
        modelo = ChecklistModelo.objects.using(db_alias).get(
            id=modelo_id,
            chmo_empr=empresa,
            chmo_fili=filial,
            chmo_ativ=True,
        )

        processo = Processo.objects.using(db_alias).create(
            proc_empr=empresa,
            proc_fili=filial,
            proc_mode=modelo,
            proc_desc=descricao,
            proc_stat=Processo.STATUS_ABERTO,
            proc_data_aber=timezone.now(),
            proc_usro_aber=usuario_id,
            proc_os = os
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
    def listar_entidades_responsaveis(*, db_alias, empresa):
        return Entidades.objects.using(db_alias).filter(
            enti_empr=empresa,
            enti_tipo_enti__in=["VE","FU"]
        )
    
    @staticmethod
    def obter_nome_responsavel(*, db_alias, empresa, processo):
        return Entidades.objects.using(db_alias).filter(
                enti_empr=empresa,
                enti_clie=processo.proc_enti_vali
            ).values_list("enti_nome", flat=True).first()