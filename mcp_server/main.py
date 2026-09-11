import os
import re
from typing import Any, Dict, List

import psycopg
from psycopg import sql as psql
from psycopg.conninfo import make_conninfo
from mcp.server.fastmcp import FastMCP

MAX_LIMIT = int(os.getenv("MAX_LIMIT", "500"))
READ_ONLY_PATTERN = re.compile(r"^\s*select\b", re.IGNORECASE)
FORBIDDEN_PATTERN = re.compile(r";|\b(insert|update|delete|drop|alter|create)\b", re.IGNORECASE)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ENCODING_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
SYSTEM_SCHEMAS = {"information_schema", "pg_catalog"}

mcp = FastMCP("ontology-mcp")


def build_dsn() -> str:
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    client_encoding = os.getenv("POSTGRES_CLIENT_ENCODING", "UTF8")
    if not all([db, user, password]):
        raise ValueError("POSTGRES_DB/USER/PASSWORD must be set in the environment.")
    if client_encoding and not ENCODING_PATTERN.fullmatch(client_encoding):
        raise ValueError("POSTGRES_CLIENT_ENCODING contains invalid characters.")

    kwargs = {
        "dbname": db,
        "user": user,
        "password": password,
        "host": host,
        "port": port,
    }
    if client_encoding:
        kwargs["options"] = f"-c client_encoding={client_encoding}"
    return make_conninfo(**kwargs)


def decode_value(value: Any) -> Any:
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        for encoding in ("utf-8", "cp949", "euc-kr"):
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="replace")
    return value


def decode_row(row: tuple) -> tuple:
    return tuple(decode_value(value) for value in row)


def fetch_all(query: Any, params: tuple = ()) -> List[Dict[str, Any]]:
    with psycopg.connect(build_dsn()) as conn:
        # String-level validation is defense in depth. The database transaction
        # itself is also read-only so every tool shares the same hard boundary.
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor(binary=True) as cur:
            cur.execute(query, params)
            colnames = [desc.name for desc in cur.description]
            rows = [decode_row(row) for row in cur.fetchall()]
            return [dict(zip(colnames, row)) for row in rows]


def parse_table_ref(table: str) -> tuple[str, str]:
    """Validate and split a public table reference without interpolating SQL."""
    parts = str(table).strip().split(".")
    if len(parts) == 1:
        schema_name, table_name = "public", parts[0]
    elif len(parts) == 2:
        schema_name, table_name = parts
    else:
        raise ValueError("Table must be provided as table or schema.table.")

    if not all(IDENTIFIER_PATTERN.fullmatch(part) for part in (schema_name, table_name)):
        raise ValueError("Table contains invalid identifier characters.")
    if schema_name.lower() in SYSTEM_SCHEMAS:
        raise ValueError("System schemas are not available through this tool.")
    return schema_name, table_name


def enforce_read_only(sql: str) -> None:
    sql = str(sql).lstrip("\ufeff").strip()
    sql = sql.rstrip(";").strip()
    if not READ_ONLY_PATTERN.match(sql):
        raise ValueError("Only SELECT statements are allowed.")
    if FORBIDDEN_PATTERN.search(sql):
        raise ValueError("Potentially unsafe SQL detected.")


@mcp.tool()
def inspect_db() -> Dict[str, Any]:
    """
    Return schema metadata for all user tables and columns.
    """
    tables = fetch_all(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
        """
    )

    columns = fetch_all(
        """
        SELECT table_schema, table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name, ordinal_position;
        """
    )

    return {"tables": tables, "columns": columns}


@mcp.tool()
def get_sample_data(table: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return a small sample from a given table.
    """
    limit = min(max(limit, 1), MAX_LIMIT)
    schema_name, table_name = parse_table_ref(table)
    query = psql.SQL("SELECT * FROM {}.{} LIMIT %s").format(
        psql.Identifier(schema_name),
        psql.Identifier(table_name),
    )
    return fetch_all(query, (limit,))


@mcp.tool()
def query_executor(sql: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Execute a read-only SQL query with a hard limit.
    """
    enforce_read_only(sql)
    limit = min(max(limit, 1), MAX_LIMIT)
    sql = str(sql).rstrip(";").strip()
    wrapped = f"SELECT * FROM ({sql}) AS q LIMIT {limit}"
    return fetch_all(wrapped)


if __name__ == "__main__":
    mcp.run()
