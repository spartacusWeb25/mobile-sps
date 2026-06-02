from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError
from core.licencas_loader import carregar_licencas_dict


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
    help = "Popula o campo enti_arqu em entidades no tenant 'pgpisos' usando dados de pedidospisos (pedi_clie -> pedi_arqu)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            type=str,
            default="pgpisos",
            help="Slug do tenant. Padrão: pgpisos",
        )

    def handle(self, *args, **options):
        slug = options.get("slug")
        licencas = carregar_licencas_dict()
        if not licencas:
            raise CommandError("Nenhuma licença encontrada")

        lics = [l for l in licencas if l.get("slug") == slug]
        if not lics:
            raise CommandError(f"Nenhuma licença encontrada para slug={slug}")
        lic = lics[0]

        alias = f"tenant_{lic['slug']}"
        connections.databases[alias] = montar_db_config(lic)

        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT 1")
        except OperationalError:
            raise CommandError(f"Banco de dados do tenant {alias} não acessível.")

        self.stdout.write(self.style.WARNING(f"Conectado ao tenant {alias}. Iniciando atualização..."))

        # Escolhe o arquiteto mais frequente por cliente (mode). Ignora pedi_arqu nulo ou zero.
        sql = '''
        WITH mf AS (
            SELECT pedi_clie, pedi_arqu
            FROM (
                SELECT pedi_clie, pedi_arqu, ROW_NUMBER() OVER (PARTITION BY pedi_clie ORDER BY COUNT(*) DESC) rn
                FROM pedidospisos
                WHERE pedi_arqu IS NOT NULL AND pedi_arqu <> 0
                GROUP BY pedi_clie, pedi_arqu
            ) t
            WHERE rn = 1
        )
        UPDATE entidades e
        SET enti_arqu = mf.pedi_arqu
        FROM mf
        WHERE e.enti_clie = mf.pedi_clie
          AND (e.enti_arqu IS NULL OR e.enti_arqu = 0);
        '''

        try:
            with connections[alias].cursor() as cursor:
                cursor.execute(sql)
                updated = cursor.rowcount
        except Exception as e:
            raise CommandError(f"Erro ao executar update: {e}")

        self.stdout.write(self.style.SUCCESS(f"Atualização concluída. Linhas afetadas: {updated}"))
        self.stdout.write(self.style.NOTICE("Observação: a lógica escolhe o arquiteto mais frequente por cliente. Se preferir outra regra (último pedido, primeiro não-nulo, etc.), informe e eu ajusto o script."))
