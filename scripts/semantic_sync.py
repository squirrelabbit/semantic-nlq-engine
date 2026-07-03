import argparse
import json
import os
from pathlib import Path

import psycopg

from semantic.semantic_layer import dataset_columns, load_mapping


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


def fetch_schema(conn: psycopg.Connection) -> dict[str, set[str]]:
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
    tables: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        tables.setdefault(table_name, set()).add(column_name)
    return tables


def is_measure(column: str) -> bool:
    if column.endswith(("_pop", "_cnt", "_sum", "_num")):
        return True
    if column.startswith(("m_", "w_")):
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync semantic_mapping.json with DB schema.")
    parser.add_argument("--mapping", default="semantic/semantic_mapping.json")
    parser.add_argument("--report", default="semantic_sync_report.json")
    parser.add_argument("--apply", action="store_true", help="Write changes back to mapping file.")
    parser.add_argument("--prune", action="store_true", help="Remove auto-added columns that no longer exist.")
    args = parser.parse_args()

    mapping_path = Path(args.mapping)
    mapping = load_mapping(mapping_path)

    with db_connect() as conn:
        schema = fetch_schema(conn)

    report = {
        "missing_tables": [],
        "added_columns": {},
        "missing_columns": {},
        "skipped_tables": [],
    }

    datasets = mapping.get("datasets", [])
    for dataset in datasets:
        table = dataset.get("table")
        if not table:
            continue
        db_cols = schema.get(table)
        if not db_cols:
            report["missing_tables"].append(table)
            continue

        current_cols = set(dataset_columns(dataset))
        missing_cols = sorted(db_cols - current_cols)
        if missing_cols:
            added = []
            dimensions = dataset.setdefault("dimensions", {})
            auto_group = dimensions.setdefault("auto", [])
            measures = dataset.setdefault("measures", [])
            for col in missing_cols:
                if is_measure(col):
                    if col not in measures:
                        measures.append(col)
                        added.append(col)
                else:
                    if col not in auto_group:
                        auto_group.append(col)
                        added.append(col)
            if added:
                report["added_columns"][table] = added

        if args.prune:
            auto_group = dataset.get("dimensions", {}).get("auto", [])
            if isinstance(auto_group, list):
                to_keep = [col for col in auto_group if col in db_cols]
                removed = sorted(set(auto_group) - set(to_keep))
                if removed:
                    report["missing_columns"][table] = removed
                dataset["dimensions"]["auto"] = to_keep

    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    if args.apply:
        mapping_path.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"Wrote report to {args.report}")
    if args.apply:
        print(f"Updated mapping: {mapping_path}")


if __name__ == "__main__":
    main()
