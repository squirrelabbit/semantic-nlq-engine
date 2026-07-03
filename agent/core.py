"""
Core implementation of the NLQ agent workflow.
"""
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .coder import plan_to_sql
from .llm_client import LLMClient
from .planner import plan_question, plan_question_two_stage


def summarize_rows(rows: object) -> dict[str, object]:
    if not isinstance(rows, list) or not rows:
        return {"summary": "No rows to summarize."}
    if not isinstance(rows[0], dict):
        return {"summary": "Rows are not structured dicts."}
    numeric_cols = {}
    for row in rows:
        for key, value in row.items():
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            stats = numeric_cols.setdefault(key, {"count": 0, "sum": 0.0, "min": num, "max": num})
            stats["count"] += 1
            stats["sum"] += num
            stats["min"] = min(stats["min"], num)
            stats["max"] = max(stats["max"], num)
    if not numeric_cols:
        return {"summary": "No numeric columns detected.", "row_count": len(rows)}
    return {"row_count": len(rows), "metrics": numeric_cols}


def is_mask_target(column: str) -> bool:
    if column.endswith(("_pop", "_cnt", "_sum", "_num")):
        return True
    if re.fullmatch(r"(m|w)_(\d{4}|70u)", column):
        return True
    return False


def parse_number(value: object) -> Optional[float]:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def apply_pii_mask(rows: object, threshold: float = 5.0) -> object:
    if not isinstance(rows, list):
        return rows
    masked_rows = []
    for row in rows:
        if not isinstance(row, dict):
            masked_rows.append(row)
            continue
        new_row = {}
        for key, value in row.items():
            num = parse_number(value)
            if num is not None and is_mask_target(key) and num < threshold:
                new_row[key] = "MASKED"
            else:
                new_row[key] = value
        masked_rows.append(new_row)
    return masked_rows


def sanitize_rows(rows: object) -> object:
    if not isinstance(rows, list):
        return rows
    sanitized = []
    for row in rows:
        if not isinstance(row, dict):
            sanitized.append(row)
            continue
        new_row = {}
        for key, value in row.items():
            if value is None:
                new_row[key] = "-"
            else:
                new_row[key] = value
        sanitized.append(new_row)
    return sanitized


def is_read_only(sql: str) -> bool:
    stripped = sql.strip().lower()
    stripped = stripped.rstrip(";").strip()
    if ";" in stripped:
        return False
    if not (stripped.startswith("select") or stripped.startswith("with")):
        return False
    blocked = ("drop ", "delete ", "update ", "insert ", "alter ", "truncate ", "create ")
    return not any(token in stripped for token in blocked)


def load_allowed_tables(mapping_path: Path) -> List[str]:
    payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    datasets = payload.get("datasets", [])
    return [str(item.get("table")) for item in datasets if item.get("table")]


def extract_sql_tables(sql: str) -> List[str]:
    normalized = re.sub(r"\\s+", " ", sql.strip())
    matches = re.findall(r"\\b(from|join)\\s+([a-zA-Z0-9_\\.]+)", normalized, flags=re.IGNORECASE)
    tables = []
    for _, token in matches:
        table = token.split(".")[-1]
        table = table.strip().strip('"')
        if table:
            tables.append(table)
    return tables


def validate_sql_tables(sql: str, mapping_path: Path) -> None:
    allowed = set(load_allowed_tables(mapping_path))
    if not allowed:
        return
    used = extract_sql_tables(sql)
    unknown = [table for table in used if table not in allowed]
    if unknown:
        raise ValueError(f"Disallowed table(s) in SQL: {', '.join(sorted(set(unknown)))}")


def resolve_mapping_path(repo_root: Path) -> Path:
    override = os.getenv("POC_MAPPING_PATH")
    if override:
        return Path(override)
    if os.getenv("POC_MODE") in ("1", "true", "TRUE"):
        poc_path = repo_root / "semantic/semantic_mapping_poc.json"
        if poc_path.exists():
            return poc_path
    return repo_root / "semantic/semantic_mapping.json"


def log_execution(
    request_id: str,
    original_question: str,
    generated_sql: str,
    execution_time: float,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    import psycopg

    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        return
    dsn = f"dbname={db} user={user} password={password} host={host} port={port}"
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO execution_logs (
                  request_id, original_question, generated_sql, execution_time, error_message, status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (request_id, original_question, generated_sql, execution_time, error_message, status),
            )
        conn.commit()


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


def decode_row(row: Tuple) -> Tuple:
    return tuple(decode_value(value) for value in row)


def execute_direct_sql(sql: str) -> List[Dict[str, Any]]:
    import psycopg

    if not is_read_only(sql):
        raise ValueError("Only SELECT/CTE statements are allowed.")

    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        raise ValueError("POSTGRES_DB/USER/PASSWORD must be set in the environment.")
    dsn = f"dbname={db} user={user} password={password} host={host} port={port}"

    with psycopg.connect(dsn) as conn:
        conn.execute("SET client_encoding TO 'UTF8'")
        with conn.cursor(binary=True) as cur:
            cur.execute(sql.replace("%", "%%"))
            colnames = [desc.name for desc in cur.description]
            rows = [decode_row(row) for row in cur.fetchall()]
            return [dict(zip(colnames, row)) for row in rows]


def build_env() -> dict[str, str]:
    env = {}
    for key in (
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_CLIENT_ENCODING",
    ):
        value = os.getenv(key)
        if value:
            env[key] = value
    return env


async def execute_mcp_sql(sql: str, repo_root: Path) -> List[Dict[str, Any]]:
    if not is_read_only(sql):
        raise ValueError("Only SELECT/CTE statements are allowed.")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server/main.py"],
        env=build_env(),
        cwd=repo_root,
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("query_executor", {"sql": sql})
            return result.structuredContent if result.structuredContent is not None else result.content


async def run_nlq_workflow(
    question: str,
    two_stage: bool = True,
    execute: bool = True,
    interpret: bool = False,
    direct: bool = False,
    repo_root: Optional[Path] = None,
    debug_mode: bool = False, # Renamed to avoid conflict with `debug` in sub-calls
) -> Dict[str, Any]:
    """
    Runs the full Natural Language Query workflow.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]
    mapping_path = resolve_mapping_path(repo_root)

    client = LLMClient()
    
    # 1. Plan
    if two_stage:
        plan, debug_plan_payload = await plan_question_two_stage(
            question,
            mapping_path,
            repo_root / "agent/plan_l1_schema.json",
            repo_root / "agent/plan_schema.json",
            client,
            debug=debug_mode,
        )
    else:
        plan, debug_plan_payload = await plan_question(
            question,
            mapping_path,
            repo_root / "agent/plan_schema.json",
            client,
            debug=debug_mode,
        )

    # 2. Code
    sql_payload, debug_code_payload = await plan_to_sql(
        plan,
        mapping_path,
        repo_root / "agent/sql_schema.json",
        client,
        debug=debug_mode, # Pass debug mode here too
    )
    sql = sql_payload.get("sql") if isinstance(sql_payload, dict) else None
    if not sql:
        notes = sql_payload.get("notes", "No details available.")
        raise ValueError(f"Failed to generate SQL from plan. Details: {notes}")
    if not is_read_only(sql):
        raise ValueError(f"Only SELECT/CTE statements are allowed. Generated SQL: {sql}")
    validate_sql_tables(sql, mapping_path)

    # 3. Execute & Interpret
    request_id = str(uuid.uuid4())
    rows = None
    insight = None
    if execute:
        start = time.perf_counter()
        try:
            if direct:
                rows = execute_direct_sql(sql)
            else:
                rows = await execute_mcp_sql(sql, repo_root)
            
            rows = sanitize_rows(apply_pii_mask(rows))
            log_execution(request_id, question, sql, time.perf_counter() - start, "SUCCESS", None)
        except Exception as exc:
            log_execution(request_id, question, sql, time.perf_counter() - start, "FAIL", str(exc))
            raise
        
        if interpret:
            insight = summarize_rows(rows)

    return {
        "plan": plan,
        "sql": sql,
        "rows": rows,
        "insight": insight,
        "request_id": request_id,
        "debug_plan_payload": debug_plan_payload if debug_mode else None, # Include debug info in return
        "debug_code_payload": debug_code_payload if debug_mode else None, # Include debug info in return
    }
