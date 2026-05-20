# marketplace/management/commands/drop_trigger_saldo_sync.py

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError
from core.licencas_loader import carregar_licencas_dict


def remover_tabela_e_trigger_saldo_sync(alias: str):
    with connections[alias].cursor() as cursor:

        cursor.execute(
            """
            DROP TRIGGER IF EXISTS trg_log_alteracao_saldo_produto
            ON saldosprodutos;
            """
        )

        cursor.execute(
            """
            DROP FUNCTION IF EXISTS fn_log_alteracao_saldo_produto();
            """
        )

        cursor.execute(
            """
            DROP TABLE IF EXISTS estoque_saldo_sync_evento;
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
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "connect_timeout": 5,
            "options": "-c statement_timeout=15000"
        }
    }


class Command(BaseCommand):
    help = "Remove trigger, function e tabela de sincronização de saldo dos tenants"

    def handle(self, *args, **options):

        licencas = carregar_licencas_dict()

        if not licencas:
            raise CommandError("Nenhuma licença encontrada")

        licencas.sort(key=lambda x: x["slug"])

        for lic in licencas:

            alias = f"tenant_{lic['slug']}"

            if not lic.get("db_host"):
                self.stdout.write(
                    self.style.ERROR(
                        f"[{alias}] Sem host configurado. Pulando..."
                    )
                )
                continue

            connections.databases[alias] = montar_db_config(lic)

            self.stdout.write(
                f"[{alias}] Conectando a {lic['db_host']}..."
            )

            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute("SELECT 1")

            except OperationalError as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{alias}] Erro de conexão: {e}. Pulando..."
                    )
                )
                continue

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{alias}] Erro genérico ao conectar: {e}. Pulando..."
                    )
                )
                continue

            self.stdout.write(
                self.style.WARNING(
                    f"[{alias}] Removendo trigger e tabela de sincronização..."
                )
            )

            try:
                remover_tabela_e_trigger_saldo_sync(alias)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{alias}] Trigger, function e tabela removidas com sucesso!"
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{alias}] Erro ao remover estruturas: {e}"
                    )
                )

            finally:
                try:
                    connections[alias].close()
                except Exception:
                    pass