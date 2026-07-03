import argparse
import json
import os
from pathlib import Path

import psycopg


def load_mapping(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def db_connect() -> psycopg.Connection:
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        raise SystemExit("POSTGRES_DB/USER/PASSWORD must be set in the environment.")
    dsn = f"dbname={db} user={user} password={password} host={host} port={port}"
    return psycopg.connect(dsn)


def fetch_schema(conn: psycopg.Connection) -> tuple[set[str], dict[str, set[str]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, column_name
            """
        )
        rows = cur.fetchall()
    tables: set[str] = set()
    columns: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        tables.add(table_name)
        columns.setdefault(table_name, set()).add(column_name)
    return tables, columns


def dataset_columns(dataset: dict) -> set[str]:
    cols: set[str] = set()
    for group in dataset.get("dimensions", {}).values():
        cols.update(group)
    cols.update(dataset.get("measures", []))
    return cols


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate semantic_mapping.json against DB schema.")
    parser.add_argument("--mapping", default="semantic/semantic_mapping.json")
    args = parser.parse_args()

    mapping = load_mapping(Path(args.mapping))
    datasets = mapping.get("datasets", [])
    with db_connect() as conn:
        tables, columns = fetch_schema(conn)

    missing_tables = []
    missing_columns = {}
    join_issues = []
    extra_columns = {}

    for dataset in datasets:
        table = dataset.get("table")
        if not table:
            continue
        if table not in tables:
            missing_tables.append(table)
            continue
        dataset_cols = dataset_columns(dataset)
        db_cols = columns.get(table, set())
        missing = sorted(dataset_cols - db_cols)
        extra = sorted(db_cols - dataset_cols)
        if missing:
            missing_columns[table] = missing
        if extra:
            extra_columns[table] = extra
        for join in dataset.get("joins", []):
            ref_table = join.get("ref_table")
            ref_column = join.get("ref_column")
            if ref_table and ref_table not in tables:
                join_issues.append(f"{table}: ref_table missing -> {ref_table}")
                continue
            if ref_table and ref_column:
                ref_cols = columns.get(ref_table, set())
                if ref_column not in ref_cols:
                    join_issues.append(f"{table}: ref_column missing -> {ref_table}.{ref_column}")

    print("Semantic Mapping Check")
    print(f"- datasets: {len(datasets)}")
    if missing_tables:
        print(f"- missing tables: {', '.join(sorted(missing_tables))}")
    if missing_columns:
        print("- missing columns:")
        for table, cols in missing_columns.items():
            print(f"  - {table}: {', '.join(cols)}")
    if join_issues:
        print("- join issues:")
        for issue in join_issues:
            print(f"  - {issue}")
    if extra_columns:
        print("- db-only columns (not in mapping):")
        for table, cols in extra_columns.items():
            print(f"  - {table}: {', '.join(cols[:10])}{' ...' if len(cols) > 10 else ''}")

    if missing_tables or missing_columns or join_issues:
        raise SystemExit("Semantic mapping validation failed.")
    print("Semantic mapping validation passed.")


if __name__ == "__main__":
    main()
