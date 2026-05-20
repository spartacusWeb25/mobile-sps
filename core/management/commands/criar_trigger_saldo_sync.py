# marketplace/management/commands/criar_trigger_saldo_sync.py

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError
from core.licencas_loader import carregar_licencas_dict


def criar_tabela_e_trigger_saldo_sync(alias: str):
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS estoque_saldo_sync_evento (
                esse_id BIGSERIAL PRIMARY KEY,

                esse_empr INTEGER,
                esse_fili INTEGER,
                esse_prod VARCHAR(120) NOT NULL,

                esse_saldo_ant NUMERIC(15, 3),
                esse_saldo_novo NUMERIC(15, 3),

                esse_status VARCHAR(20) DEFAULT 'pendente',
                esse_tent INTEGER DEFAULT 0,
                esse_erro TEXT,

                esse_cria_em TIMESTAMP DEFAULT now(),
                esse_atua_em TIMESTAMP DEFAULT now()
            );

            ALTER TABLE estoque_saldo_sync_evento
            ALTER COLUMN esse_prod TYPE VARCHAR(120)
            USING esse_prod::VARCHAR;

            CREATE INDEX IF NOT EXISTS idx_esse_status
                ON estoque_saldo_sync_evento (esse_status);

            CREATE INDEX IF NOT EXISTS idx_esse_produto
                ON estoque_saldo_sync_evento (esse_empr, esse_fili, esse_prod);

            CREATE INDEX IF NOT EXISTS idx_esse_pendente
                ON estoque_saldo_sync_evento (esse_status, esse_cria_em);
            """
        )

        cursor.execute(
            """
            CREATE OR REPLACE FUNCTION fn_log_alteracao_saldo_produto()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.sapr_sald IS DISTINCT FROM NEW.sapr_sald THEN

                    INSERT INTO estoque_saldo_sync_evento (
                        esse_empr,
                        esse_fili,
                        esse_prod,
                        esse_saldo_ant,
                        esse_saldo_novo,
                        esse_status,
                        esse_cria_em,
                        esse_atua_em
                    )
                    VALUES (
                        NEW.sapr_empr,
                        NEW.sapr_fili,
                        NEW.sapr_prod::VARCHAR,
                        OLD.sapr_sald,
                        NEW.sapr_sald,
                        'pendente',
                        now(),
                        now()
                    );

                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )

        cursor.execute(
            """
            DROP TRIGGER IF EXISTS trg_log_alteracao_saldo_produto
            ON saldosprodutos;

            CREATE TRIGGER trg_log_alteracao_saldo_produto
            AFTER UPDATE ON saldosprodutos
            FOR EACH ROW
            EXECUTE PROCEDURE fn_log_alteracao_saldo_produto();
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
    help = "Cria tabela de evento e trigger para alterações em saldosprodutos nos bancos dos tenants"

    def handle(self, *args, **options):
        licencas = carregar_licencas_dict()

        if not licencas:
            raise CommandError("Nenhuma licença encontrada")

        licencas.sort(key=lambda x: x["slug"])

        for lic in licencas:
            alias = f"tenant_{lic['slug']}"

            if not lic.get("db_host"):
                self.stdout.write(
                    self.style.ERROR(f"[{alias}] Sem host configurado. Pulando...")
                )
                continue

            connections.databases[alias] = montar_db_config(lic)

            self.stdout.write(f"[{alias}] Conectando a {lic['db_host']}...")

            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
            except OperationalError as e:
                self.stdout.write(
                    self.style.ERROR(f"[{alias}] Erro de conexão: {e}. Pulando...")
                )
                continue
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"[{alias}] Erro genérico ao conectar: {e}. Pulando...")
                )
                continue

            self.stdout.write(
                self.style.WARNING(
                    f"[{alias}] Criando tabela e trigger de sincronização de saldo..."
                )
            )

            try:
                criar_tabela_e_trigger_saldo_sync(alias)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{alias}] Tabela e trigger criadas/atualizadas com sucesso!"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{alias}] Erro ao criar tabela/trigger: {e}"
                    )
                )
            finally:
                try:
                    connections[alias].close()
                except Exception:
                    pass