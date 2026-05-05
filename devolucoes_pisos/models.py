from django.db import models

class Devolucoespedidopiso(models.Model):
    devo_empr = models.IntegerField()
    devo_fili = models.IntegerField()
    devo_pedi = models.IntegerField(primary_key=True)
    devo_data = models.DateField(blank=True, null=True)
    devo_usua = models.IntegerField(blank=True, null=True)
    devo_cred = models.BigIntegerField(blank=True, null=True)
    devo_titu = models.CharField(max_length=13, blank=True, null=True)
    devo_entr_ctrl = models.IntegerField(blank=True, null=True)
    devo_said_ctrl = models.IntegerField(blank=True, null=True)
    devo_desc = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'devolucoespedidopiso'
        unique_together = (('devo_empr', 'devo_fili', 'devo_pedi'),)




class Itensdevolucoespisos(models.Model):
    item_empr = models.IntegerField()
    item_fili = models.IntegerField()
    item_pedi = models.IntegerField()
    item_ambi = models.IntegerField()
    item_prod = models.CharField(max_length=20)
    item_m2 = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    item_quan = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    item_unit = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    item_suto = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    item_obse = models.TextField(blank=True, null=True)
    field_log_data = models.DateField(db_column='_log_data', blank=True, null=True)  # Field renamed because it started with '_'.
    field_log_time = models.TimeField(db_column='_log_time', blank=True, null=True)  # Field renamed because it started with '_'.
    item_nome_ambi = models.CharField(max_length=100, blank=True, null=True)
    item_data_entr = models.DateField(blank=True, null=True)
    item_nume = models.IntegerField(primary_key=True)
    item_nfe_fatu = models.IntegerField(blank=True, null=True)
    item_nfe_entr = models.IntegerField(blank=True, null=True)
    item_comp_efet = models.DateField(blank=True, null=True)
    item_em_esto = models.BooleanField(blank=True, null=True)
    item_caix = models.IntegerField(blank=True, null=True)
    item_stat_manu = models.CharField(max_length=30, blank=True, null=True)
    item_desc = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    item_queb = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    item_stat_manu_data = models.DateField(blank=True, null=True)
    item_stat_manu_user = models.IntegerField(blank=True, null=True)
    item_prod_nome = models.CharField(max_length=100, blank=True, null=True)
    item_ctrl_entr = models.IntegerField(blank=True, null=True)
    item_devo_data = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'itensdevolucoespisos'
        unique_together = (('item_empr', 'item_fili', 'item_pedi', 'item_ambi', 'item_prod'),)




class Creditotrocas(models.Model):
    cred_fina_empr = models.IntegerField()
    cred_fina_fili = models.IntegerField()
    cred_fina_clie = models.IntegerField()
    cred_fina_vend = models.IntegerField()
    cred_fina_data = models.DateField()
    cred_fina_es = models.IntegerField()
    cred_fina_valo = models.DecimalField(max_digits=32, decimal_places=2)
    cred_fina_obse = models.CharField(max_length=150, blank=True, null=True)
    cred_id = models.BigAutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'creditotrocas'
