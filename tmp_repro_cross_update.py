import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from decimal import Decimal

from core.licencas_loader import carregar_licencas_dict
from django.db import connections, transaction

from Pisos.models import Itensorcapisos, Orcamentopisos
from Pisos.services.orcamento_criar_service import OrcamentoCriarService
from Pisos.services.orcamento_atualizar_service import OrcamentoAtualizarService


def setup_alias(slug: str) -> str:
    lic = next(l for l in (carregar_licencas_dict() or []) if str(l.get("slug") or "").strip() == slug)
    alias = f"tenant_{slug}"
    connections.databases[alias] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": lic["db_name"],
        "USER": lic["db_user"],
        "PASSWORD": lic["db_password"],
        "HOST": lic["db_host"],
        "PORT": lic["db_port"],
    }
    return alias


def print_counts(alias: str, numero: int):
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT item_empr, item_fili, item_orca, count(*)
            FROM itensorcapisos
            WHERE item_orca = %s
            GROUP BY item_empr, item_fili, item_orca
            ORDER BY item_empr, item_fili, item_orca
            """,
            [numero],
        )
        print("COUNTS", cursor.fetchall())


def main():
    alias = setup_alias("saveweb001")

    with transaction.atomic(using=alias):
        conn = connections[alias]
        conn.force_debug_cursor = True

        orc = OrcamentoCriarService().executar(
            banco=alias,
            dados={
                "orca_empr": 1,
                "orca_fili": 2,
                "orca_clie": None,
                "orca_desc": Decimal("0"),
                "orca_fret": Decimal("0"),
                "orca_cred": Decimal("0"),
            },
            itens=[
                {
                    "item_prod": "TESTE",
                    "item_quan": Decimal("2"),
                    "item_unit": Decimal("10"),
                    "item_ambi": 1,
                },
                {
                    "item_prod": "TESTE2",
                    "item_quan": Decimal("1"),
                    "item_unit": Decimal("15"),
                    "item_ambi": 2,
                },
            ],
        )
        numero = int(orc.orca_nume)

        print("ANTES UPDATE")
        print_counts(alias, numero)

        OrcamentoAtualizarService().executar(
            banco=alias,
            orcamento=orc,
            dados={
                "orca_desc": Decimal("0"),
                "orca_fret": Decimal("0"),
                "orca_cred": Decimal("0"),
                "parametros": {},
            },
            itens=[
                {
                    "item_prod": "TESTE",
                    "item_quan": Decimal("1"),
                    "item_unit": Decimal("9"),
                    "item_ambi": 1,
                }
            ],
        )

        print("DEPOIS")
        print_counts(alias, numero)

        print("ULTIMAS QUERIES")
        for query in conn.queries[-20:]:
            print(query.get("sql"))

        transaction.set_rollback(True, using=alias)


if __name__ == "__main__":
    main()
