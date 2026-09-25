from django.db import models

class OcorrenciaTransp(models.Model):
    ocor_empr = models.IntegerField()
    ocor_fili = models.IntegerField()
    ocor_codi = models.TextField()
    ocor_desc = models.TextField()
    ocor_fina = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.ocor_codi} - {self.ocor_desc}"

    class Meta:
        managed = True
        db_table = 'ocorrencia_transp'

class PerfilOcorrencia(models.Model):
    pfoc_empr = models.IntegerField()
    pfoc_fili = models.IntegerField()
    pfoc_desc = models.TextField()
    pfoc_ativ = models.BooleanField(default=True)

    ocorrencias = models.ManyToManyField(
        "OcorrenciaTransp",
    )

    def __str__(self):
        return f"{self.pfoc_desc}"

    class Meta:
        managed = True
        db_table = 'perfil_ocorrencia'