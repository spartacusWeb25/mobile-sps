import os
import json
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("NFCE_DB_NAME")
DB_USER = os.getenv("NFCE_DB_USER")
DB_PASSWORD = os.getenv("NFCE_DB_PASSWORD")
DB_HOST = os.getenv("NFCE_DB_HOST")
DB_PORT = os.getenv("NFCE_DB_PORT", "5432")

EMPRESA = "04023617000183"

# se alguma tabela usar empr integer, pode setar no .env:
# NFCE_EMPRESA_INT=0
EMPRESA_INT = os.getenv("NFCE_EMPRESA_INT")

OUTPUT_DIR = f"dump_{EMPRESA}"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_tables(cursor):
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    return [row[0] for row in cursor.fetchall()]


def get_columns(cursor, table):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        ORDER BY ordinal_position
    """, [table])
    return [row[0] for row in cursor.fetchall()]


def get_column_type(cursor, table, column):
    cursor.execute("""
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        AND column_name = %s
    """, [table, column])
    row = cursor.fetchone()
    return row[0] if row else None


def descobrir_codigo_empresa(conn, table, campo):
    try:
        with conn.cursor() as cursor:
            query = sql.SQL("""
                SELECT DISTINCT {campo}
                FROM {table}
                WHERE {campo} IS NOT NULL
                ORDER BY {campo}
                LIMIT 20
            """).format(
                campo=sql.Identifier(campo),
                table=sql.Identifier(table),
            )
            cursor.execute(query)
            return [r[0] for r in cursor.fetchall()]
    except Exception:
        conn.rollback()
        return []


def contar_registros(conn, table, campo_empr, valor):
    with conn.cursor() as cursor:
        query = sql.SQL("""
            SELECT COUNT(*)
            FROM {table}
            WHERE {campo} = %s
        """).format(
            table=sql.Identifier(table),
            campo=sql.Identifier(campo_empr),
        )
        cursor.execute(query, [valor])
        return cursor.fetchone()[0]


def dump_table(conn, table, columns):
    campo_empr = next((c for c in columns if c.endswith("empr")), None)

    if not campo_empr:
        return 0

    with conn.cursor() as cursor:
        col_type = get_column_type(cursor, table, campo_empr)

    print(f"\n📦 {table} -> {campo_empr} ({col_type})")

    valor = EMPRESA

    if col_type in ("integer", "bigint", "smallint"):
        if EMPRESA_INT is not None:
            valor = int(EMPRESA_INT)
        else:
            candidatos = descobrir_codigo_empresa(conn, table, campo_empr)
            print(f"🔎 candidatos encontrados: {candidatos}")

            if not candidatos:
                print(f"⚠️ {table}: sem código interno")
                return 0

            valor = candidatos[0]

    try:
        total_previsto = contar_registros(conn, table, campo_empr, valor)

        if total_previsto == 0:
            print(f"⚠️ {table}: sem dados para {valor}")
            return 0

        print(f"🔢 {table}: {total_previsto} registros encontrados")

        query = sql.SQL("""
            SELECT *
            FROM {table}
            WHERE {campo} = %s
        """).format(
            table=sql.Identifier(table),
            campo=sql.Identifier(campo_empr),
        )

        file_path = os.path.join(OUTPUT_DIR, f"{table}.json")
        total = 0

        with conn.cursor(name=f"cur_{table}") as cursor:
            cursor.itersize = 1000
            cursor.execute(query, [valor])

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("[\n")

                first = True

                while True:
                    rows = cursor.fetchmany(1000)

                    if not rows:
                        break

                    for row in rows:
                        item = dict(zip(columns, row))

                        if not first:
                            f.write(",\n")

                        json.dump(item, f, ensure_ascii=False, default=str)
                        first = False
                        total += 1

                f.write("\n]")

        print(f"✔ {table}: {total} registros exportados")
        return total

    except Exception as e:
        print(f"❌ erro em {table}: {e}")
        conn.rollback()
        return 0


def main():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        connect_timeout=10
    )

    try:
        with conn.cursor() as cursor:
            tables = get_tables(cursor)

        total_tabelas = 0
        total_registros = 0

        for table in tables:
            try:
                with conn.cursor() as cursor:
                    columns = get_columns(cursor, table)

                total = dump_table(conn, table, columns)

                if total > 0:
                    total_tabelas += 1
                    total_registros += total

            except Exception as e:
                print(f"❌ erro geral em {table}: {e}")
                conn.rollback()

        print("\n==============================")
        print("✅ BACKUP FINALIZADO")
        print(f"📁 Pasta: {OUTPUT_DIR}")
        print(f"📦 Tabelas exportadas: {total_tabelas}")
        print(f"🧾 Registros exportados: {total_registros}")
        print("==============================")

    finally:
        conn.close()


if __name__ == "__main__":
    main()