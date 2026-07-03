import json
import os
import sys
from pathlib import Path

import psycopg


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def build_dsn() -> str:
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        raise ValueError("POSTGRES_DB/USER/PASSWORD must be set in the environment.")
    return f"dbname={db} user={user} password={password} host={host} port={port}"


def normalize_type(row: dict) -> str:
    data_type = row["data_type"].upper()
    char_len = row["character_maximum_length"]
    num_precision = row["numeric_precision"]
    num_scale = row["numeric_scale"]

    if data_type in ("CHARACTER VARYING", "VARCHAR"):
        if char_len:
            return f"VARCHAR({char_len})"
        return "VARCHAR"
    if data_type in ("CHARACTER", "CHAR"):
        if char_len:
            return f"CHAR({char_len})"
        return "CHAR"
    if data_type in ("NUMERIC", "DECIMAL"):
        if num_precision is not None and num_scale is not None:
            return f"NUMERIC({num_precision},{num_scale})"
        if num_precision is not None:
            return f"NUMERIC({num_precision})"
        return "NUMERIC"
    return data_type


def load_metadata(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run scripts/generate_metadata_jsonld.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    metadata = load_metadata(repo_root / "ontology/metadata.jsonld")
    graph = metadata.get("@graph", [])

    datasets = [node for node in graph if node.get("@type") == "Dataset"]
    properties = [node for node in graph if node.get("@type") == "Property"]

    prop_by_table = {}
    for prop in properties:
        table = prop.get("table")
        if not table:
            continue
        prop_by_table.setdefault(table, []).append(prop)

    with psycopg.connect(build_dsn()) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT table_name, column_name, data_type,
                       character_maximum_length, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position;
                """
            )
            schema_rows = cur.fetchall()

    schema_map = {}
    for row in schema_rows:
        schema_map.setdefault(row["table_name"], {})[row["column_name"]] = row

    errors = []

    for dataset in datasets:
        table = dataset.get("table")
        if not table:
            continue
        if table not in schema_map:
            errors.append(f"Missing table: {table}")
            continue
        for prop in prop_by_table.get(table, []):
            col = prop.get("column")
            expected_type = prop.get("dataType", "").upper()
            if col not in schema_map[table]:
                errors.append(f"Missing column: {table}.{col}")
                continue
            actual_type = normalize_type(schema_map[table][col])
            if expected_type and actual_type != expected_type:
                errors.append(f"Type mismatch: {table}.{col} expected {expected_type}, got {actual_type}")

    if errors:
        print("Schema validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Schema validation passed: tagging metadata matches database schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
