from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError

from core.licencas_loader import carregar_licencas_dict


def _criar_indices(alias: str):
    with connections[alias].cursor() as cursor:

        # =====================================================
        # PEDIDOSPISOS
        # =====================================================

        cursor.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_clie_empr_data
            ON pedidospisos (pedi_clie, pedi_empr, pedi_data);
        """)

        cursor.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_clie_empr_fili_data
            ON pedidospisos (pedi_clie, pedi_empr, pedi_fili, pedi_data);
        """)

        cursor.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_vend
            ON pedidospisos (pedi_vend);
        """)

        # =====================================================
        # ORCAMENTOPISOS
        # =====================================================

        cursor.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orcamentos_clie_empr_data
            ON orcamentopisos (orca_clie, orca_empr, orca_data);
        """)

        cursor.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orcamentos_clie_empr_fili_data
            ON orcamentopisos (orca_clie, orca_empr, orca_fili, orca_data);
        """)

        cursor.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orcamentos_vend
            ON orcamentopisos (orca_vend);
        """)

        # =====================================================
        # ENTIDADES
        # =====================================================

        cursor.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_entidades_empr_tipo
            ON entidades (enti_empr, enti_tipo_enti);
        """)

        cursor.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_entidades_vend
            ON entidades (enti_vend);
        """)


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
    help = "Cria índices para otimização da tela Clientes Sem Movimento."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            type=str,
            help="Slug do tenant específico. Se omitido, roda em todos.",
        )

        parser.add_argument(
            "--tenant",
            type=str,
            help="Alias de --slug.",
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
            raise CommandError("Nenhuma licença encontrada")

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
                    f"[{alias}] Criando índices..."
                )
            )

            try:
                _criar_indices(alias)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{alias}] Índices criados com sucesso!"
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{alias}] Erro ao criar índices: {e}"
                    )
                )