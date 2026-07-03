import os
import re
from typing import Any, Dict, List

import psycopg
from mcp.server.fastmcp import FastMCP

MAX_LIMIT = int(os.getenv("MAX_LIMIT", "500"))
READ_ONLY_PATTERN = re.compile(r"^\s*select\b", re.IGNORECASE)
FORBIDDEN_PATTERN = re.compile(r";|\b(insert|update|delete|drop|alter|create)\b", re.IGNORECASE)

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
    dsn = f"dbname={db} user={user} password={password} host={host} port={port}"
    if client_encoding:
        dsn += f" options='-c client_encoding={client_encoding}'"
    return dsn


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


def fetch_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with psycopg.connect(build_dsn()) as conn:
        client_encoding = os.getenv("POSTGRES_CLIENT_ENCODING", "UTF8")
        if client_encoding:
            conn.execute(f"SET client_encoding TO '{client_encoding}'")
        with conn.cursor(binary=True) as cur:
            safe_query = query.replace("%", "%%")
            cur.execute(safe_query, params)
            colnames = [desc.name for desc in cur.description]
            rows = [decode_row(row) for row in cur.fetchall()]
            return [dict(zip(colnames, row)) for row in rows]


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
    query = f"SELECT * FROM {table} LIMIT {limit}"
    return fetch_all(query)


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
