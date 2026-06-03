from typing import Any


from django.db import models
from django.utils.translation import gettext_lazy as _

ESTA_CHOICES = (
    ('RJ', _('RJ')),
    ('SP', _('SP')),
    ('MG', _('MG')),
    ('ES', _('ES')),
    ('PR', _('PR')),
    ('SC', _('SC')),
    ('RS', _('RS')),
    ('BA', _('BA')),
    ('PE', _('PE')),
    ('AL', _('AL')),
    ('MA', _('MA')),
    ('PI', _('PI')),
    ('RN', _('RN')),
    ('RR', _('RR')),
    ('RO', _('RO')),
    ('TO', _('TO')),
    ('PA', _('PA')),
    ('AM', _('AM')),
    ('AP', _('AP')),
    ('MT', _('MT')),
    ('MS', _('MS')),
    ('GO', _('GO')),
    ('DF', _('DF')),
)

TIPO_CHOICES = (
    ('000', _('Consumidor Final')),
    ('001', _('Consumidor Final comercio')),
    ('002', _('Consumidor Final Industria')),
    ('003', _('Revenda Comercio')),
    ('004', _('Revenda Industria')),
    ('005', _('Transportes')),
    ('006', _('Orgão Público')),
    ('007', _('Sistemas Financeiros')),
    ('008', _('Entidades Filantrópicas')),
    ('009', _('Produtoe Rural')),
    ('010', _('Orgao Público Federal')),
    ('011', _('Outros')),
)



class Tributos(models.Model):
    trib_empr = models.IntegerField(primary_key=True, verbose_name=_('Empresa'))
    trib_fili = models.IntegerField(verbose_name=_('Filial'))
    trib_tipo = models.CharField(max_length=1, 
                                 verbose_name=_('Classificação da Tributação'), 
                                 default='P')       
    trib_enti = models.CharField(max_length=3,
                                 choices=TIPO_CHOICES,
                                 default='000',
                                 verbose_name=_('Entidade'))       
    trib_esta = models.CharField(max_length=2,
                                 verbose_name=_('Estado'),
                                 choices=ESTA_CHOICES, 
                                 )        
    trib_codi = models.CharField(max_length=20,
                                 verbose_name=_('Código'))      
    trib_aliq_icms = models.DecimalField(max_digits=9, 
                                         decimal_places=4, 
                                         blank=True, null=True, 
                                         verbose_name=_('Aliquota do ICMS'))
    trib_redu_icms = models.DecimalField(max_digits=9, 
                                         decimal_places=4, 
                                         blank=True, null=True, 
                                         verbose_name=_('Redução do ICMS'))
    trib_aliq_icms_st = models.DecimalField(max_digits=9, 
                                            decimal_places=4, 
                                            blank=True, null=True, 
                                            verbose_name=_('Aliquota do ICMS ST'))
    trib_redu_icms_st = models.DecimalField(max_digits=9, 
                                            decimal_places=4, 
                                            blank=True, null=True, 
                                            verbose_name=_('Redução do ICMS ST'))
    trib_mva_icms_st = models.DecimalField(max_digits=8, 
                                            decimal_places=2, 
                                            blank=True, null=True, 
                                            verbose_name=_('MVA ICMS ST'))
    trib_men1 = models.IntegerField(blank=True, null=True, 
                                    verbose_name=_('Mensagem fiscal'))
    trib_redu_base = models.BooleanField(blank=True, null=True, 
                                        verbose_name=_('Redução da Base de Cálculo'))
    trib_cst_icms = models.CharField(max_length=3, 
                                     blank=True, null=True, 
                                     verbose_name=_('CST ICMS'))
    trib_cst_pis = models.CharField(max_length=2, 
                                     blank=True, null=True, 
                                     verbose_name=_('CST PIS'))
    trib_cst_cofi = models.CharField(max_length=2, 
                                     blank=True, null=True, 
                                     verbose_name=_('CST COFIINS'))
    trib_aliq_pis = models.DecimalField(max_digits=5, 
                                        decimal_places=2, 
                                        blank=True, null=True, 
                                        verbose_name=_('Alíquota do PIS'))
    trib_aliq_cofi = models.DecimalField(max_digits=5, 
                                        decimal_places=2, 
                                        blank=True, null=True, 
                                        verbose_name=_('Alíquota do COFINS'))
    trib_cfop = models.IntegerField(blank=True, null=True, 
                                    verbose_name=_('CFOP'))
    trib_codi_bene = models.CharField(max_length=10, blank=True, null=True, verbose_name=_('Beneficio Fiscal'))
    trib_aliq_ipi = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('Aliquota do IPI'))
    trib_cst_ipi_trib = models.CharField(max_length=2, blank=True, null=True, verbose_name=_('CST IPI'))
    trib_ibscbs_cclasstrib = models.CharField(max_length=6, blank=True, null=True, verbose_name=_('Classe Tributária'))
    trib_ibscbs_cst = models.CharField(max_length=3, blank=True, null=True, verbose_name=_('CST IBSCBS'))
    #trib_ibs_pdifuf = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    #trib_ibs_preduf = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('Redução do ICMS UF'))
    trib_ibs_paliqefetuf = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('% Alíquota Efvetiva do ICMS UF'))
    trib_ibs_pibsuf = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('PIB ICMS UF'))
    trib_ibs_pdifmun = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('Diferimento ICMS Municípal'))
    trib_ibs_paliqefetmun = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('% Alíquota Efvetiva do ICMS Municípal'))
    trib_ibs_predmun = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('% Redução do ICMS Municípal'))
    trib_adremibsret = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('% Retenção do IPI'))  
    trib_cbs_paliqefetreg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('% Alíquota Efvetiva do PIS'))
    trib_cbs_pcbs = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('% CBS'))
    trib_ibs_paliqefetmunreg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('% Alíquota Efvetiva do COFINS'))
    trib_ibs_paliqefetufreg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_('% Alíquota Efvetiva do ICMS UF'))
    trib_ibscbs_cclasstribreg = models.CharField(max_length=6, blank=True, null=True, verbose_name=_('Classe Tributária'))
    trib_ibscbs_cstreg = models.CharField(max_length=3, blank=True, null=True, verbose_name=_('CST IBSCBS'))
    trib_ibscbs_cstregid = models.IntegerField(blank=True, null=True, verbose_name=_('CST IBSCBS ID'))


    class Meta:
        managed = False
        db_table = 'tributos'
        unique_together = (('trib_empr', 'trib_fili', 'trib_tipo', 'trib_enti', 'trib_esta', 'trib_codi'),)
