from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError
from core.licencas_loader import carregar_licencas_dict

def campoPedidopisos(alias: str):
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
        ALTER TABLE IF EXISTS public.pedidospisos
            ADD COLUMN IF NOT EXISTS pedi_desc_inst_work text,
            ADD COLUMN IF NOT EXISTS pedi_data_inst_work date,
            ADD COLUMN IF NOT EXISTS pedi_data_fina_work date,
            ADD COLUMN IF NOT EXISTS pedi_desc_fina_work text,
            ADD COLUMN IF NOT EXISTS pedi_desc_comp_work text,
            ADD COLUMN IF NOT EXISTS pedi_data_comp_work date,
            ADD COLUMN IF NOT EXISTS pedi_desc_ence_work text,
            ADD COLUMN IF NOT EXISTS pedi_data_ence_work date;
 
            """
        )


def montar_db_config(lic):
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": lic["db_name"],
        "USER": lic["db_user"],
        "PASSWORD": lic["db_password"],
        "HOST": lic["db_host"],
        "PORT": lic["db_port"],
        "CONN_MAX_AGE": 60,
    }
    return config

class Command(BaseCommand):
    help = "Atualiza campos de pedido pisos"

    def handle(self, *args, **options):
        licencas = carregar_licencas_dict()

        if not licencas:
            raise CommandError("Nenhuma licença encontrada")

        for lic in licencas:
            alias = f"tenant_{lic['slug']}"
            connections.databases[alias] = montar_db_config(lic)

            # Testar conexão antes de prosseguir
            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
            except OperationalError:
                self.stdout.write(self.style.ERROR(f"[{alias}] Banco de dados não encontrado ou inacessível. Pulando..."))
                continue

            self.stdout.write(self.style.WARNING(f"[{alias}] Atualizando campos de pedido pisos..."))

            try:
                campoPedidopisos(alias)
                self.stdout.write(self.style.SUCCESS(f"[{alias}] Campos de pedido pisos atualizados com sucesso!"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{alias}] Erro ao atualizar campos de pedido pisos: {e}")) 
