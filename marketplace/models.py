from django.db import models
from django.contrib.postgres.fields import JSONField 

class MarketplaceProduto(models.Model):
    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("INTEGRANDO", "Integrando"),
        ("INTEGRADO", "Integrado"),
        ("ERRO", "Erro"),
        ("PAUSADO", "Pausado"),
    ]

    mark_empr = models.IntegerField()
    mark_fili = models.IntegerField()

    mark_prod_codi = models.CharField(max_length=60)
    mark_sku_codi = models.CharField(max_length=60)

    mark_marketplace = models.CharField(max_length=30, default="mercado_livre")
    mark_stat = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDENTE")

    mark_sync_preco = models.BooleanField(default=True)
    mark_sync_esto = models.BooleanField(default=True)

    mark_ulti_erro = models.TextField(blank=True, null=True)

    mark_criado_em = models.DateTimeField(auto_now_add=True)
    mark_atua_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marketplace_produto"
        unique_together = (
            "mark_empr",
            "mark_fili",
            "mark_prod_codi",
            "mark_marketplace",
        )
        indexes = [
            models.Index(fields=["mark_empr", "mark_fili"]),
            models.Index(fields=["mark_prod_codi"]),
            models.Index(fields=["mark_stat"]),
            models.Index(fields=["mark_marketplace"]),
        ]

    def __str__(self):
        return f"{self.mark_marketplace} - {self.mark_prod_codi} - {self.mark_stat}"



class MarketplaceAnuncio(models.Model):
    STATUS_CHOICES = [
        ("RASCUNHO", "Rascunho"),
        ("PUBLICADO", "Publicado"),
        ("PAUSADO", "Pausado"),
        ("FINALIZADO", "Finalizado"),
        ("ERRO", "Erro"),
    ]

    maan_produto = models.ForeignKey(
        MarketplaceProduto,
        on_delete=models.CASCADE,
        related_name="anuncios",
        db_column="maan_produto_id",
    )

    maan_item_id = models.CharField(max_length=60, blank=True, null=True)
    maan_titu = models.CharField(max_length=255)
    maan_cate_id = models.CharField(max_length=60, blank=True, null=True)

    maan_tipo_anun = models.CharField(max_length=30, default="gold_special")

    maan_prec = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    maan_esto = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)

    maan_stat = models.CharField(max_length=20, choices=STATUS_CHOICES, default="RASCUNHO")
    maan_url = models.CharField(max_length=255, blank=True, null=True)

    maan_payload_env = JSONField(blank=True, null=True)
    maan_payload_ret = JSONField(blank=True, null=True)

    maan_cria_em = models.DateTimeField(auto_now_add=True)
    maan_atua_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marketplace_anuncio"
        indexes = [
            models.Index(fields=["maan_item_id"]),
            models.Index(fields=["maan_stat"]),
            models.Index(fields=["maan_produto"]),
        ]

    def __str__(self):
        return f"{self.maan_titu} - {self.maan_stat}"


class MarketplaceContasMl(models.Model):
    ml_id = models.AutoField(primary_key=True)
    ml_empr = models.IntegerField()
    ml_fili = models.IntegerField()

    ml_access_token = models.CharField(max_length=255)
    ml_refresh_token = models.CharField(max_length=255)
    ml_expires_in = models.IntegerField()

    ml_created_at = models.DateTimeField(auto_now_add=True)
    ml_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "marketplace_contas_ml"
        unique_together = ("ml_empr", "ml_fili")
        indexes = [
            models.Index(fields=["ml_empr", "ml_fili"]),
            models.Index(fields=["ml_expires_in"]),
            models.Index(fields=["ml_created_at"]),
        ]

    def __str__(self):
        return f"Mercado Livre {self.ml_empr}/{self.ml_fili}"