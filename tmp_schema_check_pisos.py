import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from core.licencas_loader import carregar_licencas_dict
from django.db import connections


def main():
    slug = "saveweb001"
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

    queries = [
        (
            "constraints_itensorcapisos",
            "SELECT conname, pg_get_constraintdef(c.oid) "
            "FROM pg_constraint c "
            "JOIN pg_class t ON c.conrelid=t.oid "
            "WHERE t.relname='itensorcapisos' AND c.contype IN ('p','u') "
            "ORDER BY conname",
        ),
        (
            "constraints_itenspedidospisos",
            "SELECT conname, pg_get_constraintdef(c.oid) "
            "FROM pg_constraint c "
            "JOIN pg_class t ON c.conrelid=t.oid "
            "WHERE t.relname='itenspedidospisos' AND c.contype IN ('p','u') "
            "ORDER BY conname",
        ),
        (
            "indexes_itensorcapisos",
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename='itensorcapisos' ORDER BY indexname",
        ),
        (
            "indexes_itenspedidospisos",
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename='itenspedidospisos' ORDER BY indexname",
        ),
        (
            "triggers_itensorcapisos",
            "SELECT trigger_name, event_manipulation, action_statement "
            "FROM information_schema.triggers "
            "WHERE event_object_table='itensorcapisos' "
            "ORDER BY trigger_name",
        ),
        (
            "triggers_itenspedidospisos",
            "SELECT trigger_name, event_manipulation, action_statement "
            "FROM information_schema.triggers "
            "WHERE event_object_table='itenspedidospisos' "
            "ORDER BY trigger_name",
        ),
    ]

    with connections[alias].cursor() as cursor:
        for title, sql in queries:
            print(f"## {title}")
            cursor.execute(sql)
            rows = cursor.fetchall()
            if not rows:
                print("(sem registros)")
                continue
            for row in rows:
                print(row)


if __name__ == "__main__":
    main()
