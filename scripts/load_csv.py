import argparse
import os
import sys

import psycopg


def build_dsn() -> str:
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        raise ValueError("POSTGRES_DB/USER/PASSWORD must be set in the environment.")
    return f"dbname={db} user={user} password={password} host={host} port={port}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Load CSV into PostGIS table via COPY.")
    parser.add_argument("--table", required=True, help="Target table name")
    parser.add_argument("--csv", required=True, help="Path to CSV file")
    parser.add_argument("--columns", required=True, help="Comma-separated column list")
    parser.add_argument("--delimiter", default="|", help="CSV delimiter")
    parser.add_argument("--header", action="store_true", help="CSV has header row")
    parser.add_argument("--encoding", default="utf-8-sig", help="CSV encoding")
    args = parser.parse_args()

    csv_path = os.path.abspath(args.csv)
    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    columns = ",".join([c.strip() for c in args.columns.split(",") if c.strip()])
    if not columns:
        print("Column list is empty.", file=sys.stderr)
        return 1

    copy_sql = (
        f"COPY {args.table} ({columns}) FROM STDIN WITH "
        f"(FORMAT CSV, DELIMITER '{args.delimiter}', HEADER {str(args.header).upper()})"
    )

    with psycopg.connect(build_dsn()) as conn:
        with conn.cursor() as cur:
            with cur.copy(copy_sql) as copy:
                with open(csv_path, "r", encoding=args.encoding) as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), ""):
                        copy.write(chunk)
        conn.commit()

    print("Load complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
