from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

from core.licencas_loader import carregar_licencas_dict


def criar_tabela_plano_gerencial(alias: str):
    with connections[alias].cursor() as cursor:

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'planocontasgerencial'
            )
        """)

        tabela_existe = cursor.fetchone()[0]

        if tabela_existe:
            print(f"[{alias}] Tabela planocontasgerencial já existe.")
            return

        cursor.execute("""
            CREATE TABLE public.planocontasgerencial (
                gere_empr INTEGER NOT NULL,
                gere_redu INTEGER NOT NULL,

                gere_niv1 INTEGER NULL,
                gere_expa VARCHAR(60) NULL,
                gere_grup VARCHAR(60) NULL,
                gere_nive INTEGER NULL,
                gere_anal CHAR(1) NULL,
                gere_natu CHAR(2) NULL,
                gere_refe VARCHAR(60) NULL,

                gere_dati DATE NULL,
                gere_data DATE NULL,

                gere_inat BOOLEAN NULL,
                gere_data_inat DATE NULL,

                gere_obse TEXT NULL,
                gere_nome VARCHAR(60) NULL,

                gere_dre CHAR(2) NULL,
                gere_natu_sped CHAR(2) NULL,

                gere_de INTEGER NULL,

                CONSTRAINT pk_planocontasgerencial
                    PRIMARY KEY (gere_empr, gere_redu)
            );
        """)

        print(f"[{alias}] Tabela planocontasgerencial criada com sucesso.")


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
    help = "Cria a tabela planocontasgerencial em todos os bancos caso não exista"

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            type=str,
            help="Slug do tenant específico"
        )

        parser.add_argument(
            "--tenant",
            type=str,
            help="Alias de --slug"
        )

    def handle(self, *args, **options):

        slug = options.get("slug")
        tenant = options.get("tenant")

        if slug and tenant and slug != tenant:
            raise CommandError(
                "Use apenas um entre --slug e --tenant."
            )

        slug_alvo = slug or tenant

        licencas = carregar_licencas_dict()

        if not licencas:
            raise CommandError("Nenhuma licença encontrada.")

        if slug_alvo:
            licencas = [
                l for l in licencas
                if l.get("slug") == slug_alvo
            ]

            if not licencas:
                raise CommandError(
                    f"Nenhuma licença encontrada para slug={slug_alvo}"
                )

        for lic in licencas:

            alias = f"tenant_{lic['slug']}"

            connections.databases[alias] = montar_db_config(lic)

            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute("SELECT 1")

            except OperationalError:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{alias}] Banco inacessível. Pulando..."
                    )
                )
                continue

            self.stdout.write(
                self.style.WARNING(
                    f"[{alias}] Verificando tabela planocontasgerencial..."
                )
            )

            try:
                criar_tabela_plano_gerencial(alias)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{alias}] Processo concluído com sucesso!"
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{alias}] Erro ao criar tabela: {e}"
                    )
                )