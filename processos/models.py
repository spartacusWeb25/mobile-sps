# processos/models.py

from django.db import models


class ChecklistModelo(models.Model):
    chmo_empr = models.IntegerField()
    chmo_fili = models.IntegerField()

    chmo_nome = models.CharField(max_length=120)
    chmo_ativ = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.chmo_nome}"

    class Meta:
        db_table = "checklist_modelo"


class ChecklistItem(models.Model):
    chit_empr = models.IntegerField()
    chit_fili = models.IntegerField()

    chit_mode = models.ForeignKey(
        ChecklistModelo,
        on_delete=models.DO_NOTHING,
        db_column="chit_mode",
        related_name="itens",
    )

    chit_desc = models.CharField(max_length=255)
    chit_obri = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.chit_mode.chmo_nome} - {self.chit_desc}"

    class Meta:
        db_table = "checklist_item"


class Processo(models.Model):
    STATUS_ABERTO = "ABERTO"
    STATUS_EM_VALIDACAO = "EM_VALIDACAO"
    STATUS_APROVADO = "APROVADO"
    STATUS_REPROVADO = "REPROVADO"
    STATUS_CANCELADO = "CANCELADO"

    STATUS_CHOICES = (
        (STATUS_ABERTO, "Aberto"),
        (STATUS_EM_VALIDACAO, "Em validação"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_REPROVADO, "Reprovado"),
        (STATUS_CANCELADO, "Cancelado"),
    )

    proc_empr = models.IntegerField()
    proc_fili = models.IntegerField()

    proc_mode = models.ForeignKey(
        ChecklistModelo,
        on_delete=models.DO_NOTHING,
        db_column="proc_mode",
    )

    proc_desc = models.CharField(max_length=255, null=True, blank=True)
    proc_stat = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ABERTO,
    )

    proc_data_aber = models.DateTimeField(auto_now_add=True)
    proc_data_fech = models.DateTimeField(null=True, blank=True)

    proc_vers = models.IntegerField(null=True, blank=True)
    proc_usro_aber = models.IntegerField(null=True, blank=True)
    proc_usro_vali = models.IntegerField(null=True, blank=True)
    proc_enti_vali = models.IntegerField(null=True, blank=True)
    proc_os = models.ForeignKey(
        'O_S.Os',
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        db_column='proc_os',
        db_constraint=False
    )

    def __str__(self):
        return f"{self.proc_mode.chmo_nome} - {self.proc_desc}"

    class Meta:
        db_table = "processo"


class ProcessoChecklistResposta(models.Model):
    RESP_SIM = "SIM"
    RESP_NAO = "NAO"
    RESP_NA = "NA"

    RESPOSTA_CHOICES = (
        (RESP_SIM, "Sim"),
        (RESP_NAO, "Não"),
        (RESP_NA, "Não se aplica"),
    )

    pchr_empr = models.IntegerField()
    pchr_fili = models.IntegerField()

    pchr_proc = models.ForeignKey(
        Processo,
        on_delete=models.CASCADE,
        db_column="pchr_proc",
        related_name="respostas",
    )

    pchr_item = models.ForeignKey(
        ChecklistItem,
        on_delete=models.SET_NULL,
        null=True,
        db_column="pchr_item",
    )

    pchr_resp = models.CharField(
        max_length=3,
        choices=RESPOSTA_CHOICES,
        null=True,
        blank=True,
    )

    pchr_obse = models.TextField(null=True, blank=True)

    pchr_desc = models.CharField(max_length=255, null=True, blank=True)
    pchr_obri = models.BooleanField(default=False)

    pchr_vers = models.IntegerField(null=True, blank=True)
    pchr_vali = models.BooleanField(default=False)
    pchr_data_vali = models.DateTimeField(null=True, blank=True)
    pchr_usro_vali = models.IntegerField(null=True, blank=True)
    pchr_enti_vali = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.pchr_proc.proc_mode.chmo_nome} - {self.pchr_item.chit_desc} - {self.pchr_resp}"

    class Meta:
        db_table = "processo_checklist_resposta"