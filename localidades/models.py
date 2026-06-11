from django.db import models


class Estados(models.Model):
    esta_codi = models.IntegerField(primary_key=True, verbose_name='Código do Estado')
    esta_nome = models.CharField(max_length=255, verbose_name='Nome do Estado')
    esta_sigl = models.CharField(max_length=2, verbose_name='Sigla do Estado')


    class Meta:
        managed = False
        db_table = 'estados'
    
    def __str__(self):
        return self.esta_sigl + ' - ' + self.esta_nome
        

class Paises(models.Model):
    pais_codi = models.IntegerField(primary_key=True, verbose_name='Código do País')
    pais_nome = models.CharField(max_length=255, verbose_name='Nome do País')
    pais_obse = models.TextField(blank=True, null=True, verbose_name='Observações')

    

    class Meta:
        managed = False
        db_table = 'paises'
        
    def __str__(self):
        return self.pais_sigl + ' - ' + self.pais_nome
        


class Cidades(models.Model):
    cida_codi = models.IntegerField(primary_key=True, verbose_name='Código da Cidade')
    cida_nome = models.CharField(max_length=255, verbose_name='Nome da Cidade')
    cida_esta = models.ForeignKey('Estados', models.DO_NOTHING, db_column='cida_esta', verbose_name='Estado da Cidade')
    cida_pais = models.ForeignKey('Paises', models.DO_NOTHING, db_column='cida_pais', verbose_name='País da Cidade')
    cida_sigl = models.CharField(max_length=2, verbose_name='Sigla da Cidade')
    cida_fret = models.IntegerField(blank=True, null=True, verbose_name='Frete da Cidade')

    class Meta:
        managed = False
        db_table = 'cidades'
        verbose_name = 'Cidade'
        verbose_name_plural = 'Cidades'
        
    def __str__(self):
        return self.cida_sigl + ' - ' + self.cida_nome
        