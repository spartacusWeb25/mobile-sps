r"""
Importa arquivos JSON de um dump para o banco do tenant selecionado (multidb/multislug).

Pré-requisito (Windows):
  cd d:\mobile-sps
  .\.venv\Scripts\activate

Exemplos:
  # Simular (não grava)
  python manage.py import_dump_to_tenant --slug saveweb006 --dump-path d:\mobile-sps\dump_04023617000183 --dry-run

  # Importar tudo do dump
  python manage.py import_dump_to_tenant --slug saveweb006 --dump-path d:\mobile-sps\dump_04023617000183

  # Importar apenas alguns arquivos (sem extensão)
  python manage.py import_dump_to_tenant --slug saveweb006 --dump-path d:\mobile-sps\dump_04023617000183 --files entidades filiais usuarios produtos

Notas:
  - O loader aceita JSON válido e também dumps no formato "[" + objetos sequenciais sem vírgula entre eles.
  - Por padrão, arquivos cujo nome não corresponde a uma tabela existente no tenant são ignorados.
  
  python manage.py import_dump_to_tenant --slug saveweb006 --dump-path d:\mobile-sps\dump_04023617000183 --empresa-id 2 --filial-id 3 caso precise especificar uma empresa ou filial específica.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.db.utils import OperationalError

from core.licencas_loader import carregar_licencas_dict

def montar_db_config(lic: dict[str, Any]) -> dict[str, Any]:
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": lic["db_name"],
        "USER": lic["db_user"],
        "PASSWORD": lic["db_password"],
        "HOST": lic["db_host"],
        "PORT": lic["db_port"],
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=600000",
        },
    }


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _is_empresa_column(column_name: str) -> bool:
    c = (column_name or "").lower()
    return c.endswith("_empr") or c in {"empr", "empresa", "empresa_id"}


def _is_filial_column(column_name: str) -> bool:
    c = (column_name or "").lower()
    return c.endswith("_fili") or c in {"fili", "filial", "filial_id"}


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if not text:
        return []

    text = text.lstrip("\ufeff")

    def _as_list_of_dicts(v: Any) -> list[dict[str, Any]] | None:
        if v is None:
            return []
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
        if isinstance(v, dict):
            inner = v.get("data")
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
        return None

    try:
        data = json.loads(text)
        as_list = _as_list_of_dicts(data)
        if as_list is None:
            raise ValueError("JSON inválido (esperado lista de objetos)")
        return as_list
    except json.JSONDecodeError:
        s = text.lstrip()
        if not s.startswith("["):
            raise

        decoder = json.JSONDecoder()
        idx = 1
        n = len(s)
        items: list[dict[str, Any]] = []

        while idx < n:
            while idx < n and s[idx].isspace():
                idx += 1
            if idx >= n:
                break
            if s[idx] == "]":
                break
            if s[idx] == ",":
                idx += 1
                continue

            obj, next_idx = decoder.raw_decode(s, idx)
            idx = next_idx
            if isinstance(obj, dict):
                items.append(obj)

        return items


def _existing_tables(alias: str) -> set[str]:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            """
        )
        return {r[0] for r in cursor.fetchall()}


def _columns_info(alias: str, table: str) -> dict[str, dict[str, str]]:
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            [table],
        )
        return {r[0]: {"data_type": r[1], "udt_name": r[2]} for r in cursor.fetchall()}


def _coerce_value(value: Any, *, data_type: str, udt_name: str) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip() == "":
            if data_type in {
                "integer",
                "bigint",
                "smallint",
                "numeric",
                "double precision",
                "real",
                "date",
                "timestamp without time zone",
                "timestamp with time zone",
                "time without time zone",
                "time with time zone",
                "boolean",
                "uuid",
            }:
                return None
        if data_type == "boolean":
            lower = value.strip().lower()
            if lower in {"t", "true", "1", "yes", "y"}:
                return True
            if lower in {"f", "false", "0", "no", "n"}:
                return False
    if udt_name in {"json", "jsonb"} and isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _insert_rows(
    *,
    alias: str,
    table: str,
    rows: list[dict[str, Any]],
    truncate: bool,
    batch_size: int,
    empresa_id: int,
    filial_id: int,
) -> int:
    cols_meta = _columns_info(alias, table)
    if not cols_meta:
        return 0

    table_q = _quote_ident(table)
    cols_available = list(cols_meta.keys())

    filtered: list[dict[str, Any]] = []
    for r in rows:
        item = {k: v for k, v in r.items() if k in cols_meta}
        if item:
            filtered.append(item)

    if not filtered:
        return 0

    keys_present = set()
    for r in filtered:
        keys_present.update(r.keys())
    columns = [
        c
        for c in cols_available
        if c in keys_present or _is_empresa_column(c) or _is_filial_column(c)
    ]
    if not columns:
        return 0

    columns_q = ", ".join(_quote_ident(c) for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table_q} ({columns_q}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    inserted = 0
    with connections[alias].cursor() as cursor:
        if truncate:
            cursor.execute(f"TRUNCATE TABLE {table_q} RESTART IDENTITY CASCADE")

        for i in range(0, len(filtered), batch_size):
            chunk = filtered[i : i + batch_size]
            params = []
            for r in chunk:
                row_values = []
                for c in columns:
                    meta = cols_meta[c]
                    if _is_empresa_column(c):
                        v = empresa_id
                    elif _is_filial_column(c):
                        v = filial_id
                    else:
                        v = r.get(c)
                    row_values.append(
                        _coerce_value(
                            v,
                            data_type=meta["data_type"],
                            udt_name=meta["udt_name"],
                        )
                    )
                params.append(tuple(row_values))
            cursor.executemany(sql, params)
            inserted += len(chunk)

    return inserted


def _fix_serial_sequences(alias: str, table: str) -> int:
    fixed = 0
    table_q = table
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_default LIKE 'nextval(%'
            """,
            [table],
        )
        serial_cols = [r[0] for r in cursor.fetchall()]
        for col in serial_cols:
            cursor.execute("SELECT pg_get_serial_sequence(%s, %s)", [table_q, col])
            seq = cursor.fetchone()
            if not seq or not seq[0]:
                continue
            seq_name = seq[0]
            cursor.execute(
                f"SELECT COALESCE(MAX({_quote_ident(col)}), 0) FROM {_quote_ident(table)}"
            )
            max_val = cursor.fetchone()[0] or 0
            cursor.execute("SELECT setval(%s, %s, true)", [seq_name, int(max_val)])
            fixed += 1
    return fixed


class Command(BaseCommand):
    help = "Importa arquivos JSON do dump para o banco do tenant selecionado (multidb/multislug)."

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, help="Slug do tenant (ex: saveweb006).")
        parser.add_argument("--tenant", type=str, help="Alias de --slug (compatibilidade).")
        parser.add_argument("--cnpj", type=str, help="CNPJ do tenant (somente dígitos ou formatado).")
        parser.add_argument(
            "--dump-path",
            type=str,
            default=str(Path("dump_04023617000183")),
            help="Caminho do diretório com os JSONs (ex: d:\\mobile-sps\\dump_04023617000183).",
        )
        parser.add_argument(
            "--files",
            nargs="*",
            default=[],
            help="Lista de arquivos (sem extensão) para importar. Se omitido, importa todos do diretório.",
        )
        parser.add_argument("--empresa-id", type=int, default=1, help="Valor fixo para colunas de empresa (*_empr).")
        parser.add_argument("--filial-id", type=int, default=1, help="Valor fixo para colunas de filial (*_fili).")
        parser.add_argument("--truncate", action="store_true", help="Trunca tabelas antes de importar.")
        parser.add_argument("--dry-run", action="store_true", help="Valida e mostra o plano sem gravar.")
        parser.add_argument("--batch-size", type=int, default=500, help="Tamanho do lote do INSERT.")
        parser.add_argument("--skip-missing-tables", action="store_true", default=True, help="Pula arquivos cuja tabela não existe no banco.")
        parser.add_argument("--no-skip-missing-tables", action="store_false", dest="skip_missing_tables", help="Falha se algum arquivo referenciar tabela ausente.")
        parser.add_argument("--no-fix-sequences", action="store_true", help="Não ajusta sequences seriais ao final.")

    def handle(self, *args, **options):
        slug = options.get("slug")
        tenant = options.get("tenant")
        if slug and tenant and slug != tenant:
            raise CommandError("Use apenas um entre --slug e --tenant (ou informe o mesmo valor em ambos).")
        slug_alvo = slug or tenant

        cnpj = options.get("cnpj")
        dump_path = Path(options["dump_path"]).expanduser().resolve()
        files_filter: list[str] = options.get("files") or []
        truncate: bool = bool(options.get("truncate"))
        dry_run: bool = bool(options.get("dry_run"))
        batch_size: int = int(options.get("batch_size") or 500)
        skip_missing_tables: bool = bool(options.get("skip_missing_tables"))
        fix_sequences: bool = not bool(options.get("no_fix_sequences"))
        empresa_id: int = int(options.get("empresa_id") or 1)
        filial_id: int = int(options.get("filial_id") or 1)

        if not dump_path.exists() or not dump_path.is_dir():
            raise CommandError(f"Diretório de dump inválido: {dump_path}")

        if not slug_alvo and not cnpj:
            raise CommandError("Informe --slug/--tenant ou --cnpj para selecionar o tenant.")

        licencas = carregar_licencas_dict()
        if not licencas:
            raise CommandError("Nenhuma licença encontrada")

        alvo = None
        if slug_alvo:
            alvo = next((l for l in licencas if l.get("slug") == slug_alvo), None)
            if not alvo:
                raise CommandError(f"Nenhuma licença encontrada para slug={slug_alvo}")
        else:
            norm = "".join(ch for ch in str(cnpj) if ch.isdigit())
            alvo = next((l for l in licencas if "".join(ch for ch in str(l.get('cnpj') or '') if ch.isdigit()) == norm), None)
            if not alvo:
                raise CommandError(f"Nenhuma licença encontrada para cnpj={cnpj}")
            slug_alvo = alvo.get("slug")

        alias = f"tenant_{slug_alvo}"
        if not alvo.get("db_host"):
            raise CommandError(f"[{alias}] Sem host configurado.")

        connections.databases[alias] = montar_db_config(alvo)

        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT 1")
        except OperationalError as e:
            raise CommandError(f"[{alias}] Banco de dados não encontrado ou inacessível: {e}")
        except Exception as e:
            raise CommandError(f"[{alias}] Erro ao conectar: {e}")

        json_files = sorted(dump_path.glob("*.json"), key=lambda p: p.name.lower())
        if files_filter:
            wanted = {f.lower().removesuffix(".json") for f in files_filter}
            json_files = [p for p in json_files if p.stem.lower() in wanted]
            if not json_files:
                raise CommandError("Nenhum arquivo corresponde a --files.")

        order_preference = [
            "cfop",
            "unidadesmedidas",
            "tributos",
            "series",
            "entidades",
            "filiais",
            "usuarios",
            "permissoes",
            "produtos",
            "saldosprodutos",
            "caixageral",
            "formarecebimento",
            "movicaixa",
            "movimentoestoque",
            "vlog",
        ]
        pref_index = {name: idx for idx, name in enumerate(order_preference)}
        json_files.sort(key=lambda p: (pref_index.get(p.stem.lower(), 999), p.name.lower()))

        tables = _existing_tables(alias)

        total_inserted = 0
        total_files = 0
        skipped_files: list[str] = []
        fixed_sequences = 0

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[{alias}] DRY-RUN: nenhuma alteração será gravada."))

        try:
            with transaction.atomic(using=alias):
                for p in json_files:
                    table = p.stem.lower()
                    if table not in tables:
                        msg = f"[{alias}] Tabela ausente: {table} (arquivo {p.name})"
                        if skip_missing_tables:
                            skipped_files.append(msg)
                            continue
                        raise CommandError(msg)

                    try:
                        rows = _load_json_list(p)
                    except Exception as e:
                        raise CommandError(f"[{alias}] Falha ao ler {p.name}: {e}")

                    if not rows:
                        total_files += 1
                        self.stdout.write(f"[{alias}] {p.name}: vazio (0)")
                        continue

                    if dry_run:
                        total_files += 1
                        self.stdout.write(f"[{alias}] {p.name} -> {table}: {len(rows)} registros (simulado)")
                        continue

                    inserted = _insert_rows(
                        alias=alias,
                        table=table,
                        rows=rows,
                        truncate=truncate,
                        batch_size=batch_size,
                        empresa_id=empresa_id,
                        filial_id=filial_id,
                    )
                    total_inserted += inserted
                    total_files += 1
                    self.stdout.write(self.style.SUCCESS(f"[{alias}] {p.name} -> {table}: {inserted} registros"))

                    if fix_sequences:
                        try:
                            fixed_sequences += _fix_serial_sequences(alias, table)
                        except Exception:
                            pass

                if dry_run:
                    transaction.set_rollback(True, using=alias)
        finally:
            try:
                connections[alias].close()
            except Exception:
                pass

        if skipped_files:
            for s in skipped_files:
                self.stdout.write(self.style.WARNING(s))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"[{alias}] DRY-RUN concluído: {total_files} arquivos analisados."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"[{alias}] Importação concluída: {total_files} arquivos, {total_inserted} registros, sequences ajustadas: {fixed_sequences}"
            )
        )

