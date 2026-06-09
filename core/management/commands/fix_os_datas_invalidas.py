from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

from core.licencas_loader import carregar_licencas_dict


def _fix_table(alias: str):
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            UPDATE os
            SET
                os_data_aber = CASE
                    WHEN os_data_aber IS NULL OR EXTRACT(YEAR FROM os_data_aber) NOT BETWEEN 1900 AND 2100
                        THEN CURRENT_DATE
                    ELSE os_data_aber
                END,
                os_data_entr = CASE
                    WHEN os_data_entr IS NOT NULL AND EXTRACT(YEAR FROM os_data_entr) NOT BETWEEN 1900 AND 2100
                        THEN NULL
                    ELSE os_data_entr
                END,
                os_data_fech = CASE
                    WHEN os_data_fech IS NOT NULL AND EXTRACT(YEAR FROM os_data_fech) NOT BETWEEN 1900 AND 2100
                        THEN NULL
                    ELSE os_data_fech
                END,
                _log_data = CASE
                    WHEN _log_data IS NOT NULL AND EXTRACT(YEAR FROM _log_data) NOT BETWEEN 1900 AND 2100
                        THEN NULL
                    ELSE _log_data
                END
            WHERE
                os_data_aber IS NULL
                OR EXTRACT(YEAR FROM os_data_aber) NOT BETWEEN 1900 AND 2100
                OR (os_data_entr IS NOT NULL AND EXTRACT(YEAR FROM os_data_entr) NOT BETWEEN 1900 AND 2100)
                OR (os_data_fech IS NOT NULL AND EXTRACT(YEAR FROM os_data_fech) NOT BETWEEN 1900 AND 2100)
                OR (_log_data IS NOT NULL AND EXTRACT(YEAR FROM _log_data) NOT BETWEEN 1900 AND 2100);
            """
        )


def montar_db_config(lic):
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": lic["db_name"],
        "USER": lic["db_user"],
        "PASSWORD": lic["db_password"],
        "HOST": lic["db_host"],
        "PORT": lic["db_port"],
        "CONN_MAX_AGE": 60,
    }


class Command(BaseCommand):
    help = "Corrige datas invalidas na tabela os para todos os tenants ou um tenant especifico."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            type=str,
            help="Slug do tenant especifico. Se omitido, roda em todos os tenants.",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            help="Alias de --slug (compatibilidade).",
        )

    def handle(self, *args, **options):
        slug = options.get("slug")
        tenant = options.get("tenant")
        if slug and tenant and slug != tenant:
            raise CommandError("Use apenas um entre --slug e --tenant (ou informe o mesmo valor em ambos).")

        slug_alvo = slug or tenant
        licencas = carregar_licencas_dict()
        if not licencas:
            raise CommandError("Nenhuma licenca encontrada")

        if slug_alvo:
            licencas = [l for l in licencas if l.get("slug") == slug_alvo]
            if not licencas:
                raise CommandError(f"Nenhuma licenca encontrada para slug={slug_alvo}")

        for lic in licencas:
            alias = f"tenant_{lic['slug']}"
            connections.databases[alias] = montar_db_config(lic)

            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
            except OperationalError:
                self.stdout.write(self.style.ERROR(f"[{alias}] Banco de dados nao encontrado ou inacessivel. Pulando..."))
                continue

            self.stdout.write(self.style.WARNING(f"[{alias}] Corrigindo datas invalidas da tabela os..."))
            try:
                _fix_table(alias)
                self.stdout.write(self.style.SUCCESS(f"[{alias}] Datas da tabela os corrigidas com sucesso!"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{alias}] Erro ao corrigir datas da tabela os: {e}"))
