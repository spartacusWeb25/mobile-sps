from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Notas_Fiscais", "0005_nota_chave_referenciada"),
    ]

    operations = [
        migrations.AddField(
            model_name="notaitem",
            name="beneficio_fiscal",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name="notaitem",
            name="ibscbs_cst",
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
        migrations.AddField(
            model_name="notaitem",
            name="ibscbs_cclasstrib",
            field=models.CharField(blank=True, max_length=6, null=True),
        ),
    ]

