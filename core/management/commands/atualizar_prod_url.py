from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError
from core.licencas_loader import carregar_licencas_dict
import csv
import os


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


def atualizar_prod_url(alias: str, csv_path: str):
    """Atualiza o campo prod_url na tabela produtos usando o CSV"""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")

    with connections[alias].cursor() as cursor:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            updated = 0
            
            for row in reader:
                codigo = row.get('codigo')
                prod_url = row.get('prod_url', '')
                
                if not codigo:
                    continue
                
                cursor.execute(
                    """
                    UPDATE produtos
                    SET prod_url = %s
                    WHERE prod_codi = %s
                    """,
                    [prod_url, codigo]
                )
                
                if cursor.rowcount > 0:
                    updated += cursor.rowcount
                    count += 1
            
            return count, updated


class Command(BaseCommand):
    help = "Atualiza o campo prod_url na tabela produtos usando CSV gerado pelo importa_produtos (por tenant ou todos)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            type=str,
            help="Slug do tenant específico. Se omitido, roda em todos os tenants.",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            help="Alias de --slug (compatibilidade).",
        )
        parser.add_argument(
            "--csv",
            type=str,
            required=True,
            help="Caminho para o arquivo CSV com as URLs (ex: produtos_com_url_pgpisos.csv)",
        )

    def handle(self, *args, **options):
        slug = options.get("slug")
        tenant = options.get("tenant")
        csv_path = options.get("csv")
        
        if slug and tenant and slug != tenant:
            raise CommandError("Use apenas um entre --slug e --tenant (ou informe o mesmo valor em ambos).")

        slug_alvo = slug or tenant
        licencas = carregar_licencas_dict()

        if not licencas:
            raise CommandError("Nenhuma licença encontrada")

        if slug_alvo:
            licencas = [l for l in licencas if l.get("slug") == slug_alvo]
            if not licencas:
                raise CommandError(f"Nenhuma licença encontrada para slug={slug_alvo}")

        total_atualizados = 0
        total_produtos = 0

        for lic in licencas:
            alias = f"tenant_{lic['slug']}"
            connections.databases[alias] = montar_db_config(lic)

            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
            except OperationalError:
                self.stdout.write(self.style.ERROR(f"[{alias}] Banco de dados não encontrado ou inacessível. Pulando..."))
                continue

            self.stdout.write(self.style.WARNING(f"[{alias}] Atualizando prod_url do CSV: {csv_path}"))
            
            try:
                count, updated = atualizar_prod_url(alias, csv_path)
                total_produtos += count
                total_atualizados += updated
                self.stdout.write(self.style.SUCCESS(f"[{alias}] {count} produtos atualizados ({updated} linhas afetadas)"))
            except FileNotFoundError as e:
                self.stdout.write(self.style.ERROR(f"[{alias}] {e}"))
                continue
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{alias}] Erro ao atualizar prod_url: {e}"))
                continue

        self.stdout.write("\n" + self.style.WARNING("═" * 65))
        self.stdout.write(self.style.WARNING("  RESUMO"))
        self.stdout.write(self.style.WARNING("═" * 65))
        self.stdout.write(f"  Produtos processados: {total_produtos}")
        self.stdout.write(f"  Linhas atualizadas: {total_atualizados}")
