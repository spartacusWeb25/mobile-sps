# Versão idempotente: usa ADD COLUMN IF NOT EXISTS para tolerar colunas já criadas manualmente.

from django.db import migrations, models


def _adicionar_colunas_seguro(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE IF EXISTS nf_nota_item
                ADD COLUMN IF NOT EXISTS beneficio_fiscal VARCHAR(10) NULL,
                ADD COLUMN IF NOT EXISTS ibscbs_cst VARCHAR(3) NULL,
                ADD COLUMN IF NOT EXISTS ibscbs_cclasstrib VARCHAR(6) NULL;
            """
        )


def _noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("Notas_Fiscais", "0005_nota_chave_referenciada"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_adicionar_colunas_seguro, _noop_reverse),
            ],
            state_operations=[
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
            ],
        ),
    ]