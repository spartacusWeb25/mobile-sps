from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

from core.licencas_loader import carregar_licencas_dict


def _alter_table(alias: str):
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            alter table os
            add column if not exists os_tota numeric(15,2) default 0,
            add column if not exists os_assi_clie bytea,
            add column if not exists os_assi_oper bytea;
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
    help = "Cria os campos os_tota, os_assi_clie e os_assi_oper na tabela os para todos os tenants (ou um especifico)."

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

            self.stdout.write(self.style.WARNING(f"[{alias}] Atualizando tabela os (os_tota, os_assi_clie, os_assi_oper)..."))
            try:
                _alter_table(alias)
                self.stdout.write(self.style.SUCCESS(f"[{alias}] Campos da tabela os atualizados com sucesso!"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{alias}] Erro ao atualizar campos da tabela os: {e}"))
