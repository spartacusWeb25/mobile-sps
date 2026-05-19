from django.db import models
from django.contrib.postgres.fields import JSONField 



class PlanoGerencialMascara(models.Model):
    gere_empr = models.IntegerField()
    gere_nome = models.CharField(max_length=60, default="Plano Gerencial")
    gere_nive = JSONField(default=list, verbose_name="Níveis")
    gere_ativ = models.BooleanField(default=True, verbose_name="Ativo")

    gere_cria_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    gere_atual_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        db_table = "plano_gerencial_mascara"
        constraints = [
            models.UniqueConstraint(
                fields=["gere_empr"],
                condition=models.Q(gere_ativ=True),
                name="unique_mascara_gerencial_ativa_por_empresa",
            )
        ]

    def __str__(self):
        return f"{self.gere_empr} - {self.gere_nome}"

class PlanoGerencialConta(models.Model):
    gere_empr = models.IntegerField(primary_key=True)
    gere_redu = models.IntegerField()
    gere_niv1 = models.IntegerField(blank=True, null=True)
    gere_expa = models.CharField(max_length=60, blank=True, null=True)
    gere_grup = models.CharField(max_length=60, blank=True, null=True)
    gere_nive = models.IntegerField(blank=True, null=True)
    gere_anal = models.CharField(max_length=1, blank=True, null=True)
    gere_natu = models.CharField(max_length=2, blank=True, null=True)
    gere_refe = models.CharField(max_length=60, blank=True, null=True)
    gere_dati = models.DateField(blank=True, null=True)
    gere_data = models.DateField(blank=True, null=True)
    gere_inat = models.BooleanField(blank=True, null=True)
    gere_data_inat = models.DateField(blank=True, null=True)
    gere_obse = models.TextField(blank=True, null=True)
    gere_nome = models.CharField(max_length=60, blank=True, null=True)
    gere_dre = models.CharField(max_length=2, blank=True, null=True)
    gere_natu_sped = models.CharField(max_length=2, blank=True, null=True)
    gere_de = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'planocontasgerencial'
        unique_together = (('gere_empr', 'gere_redu'),)

    def __str__(self):
        return f"{self.gere_empr} - {self.gere_redu} - {self.gere_nome}"