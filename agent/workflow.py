import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent.coder import plan_to_sql
from agent.llm_client import LLMClient
from agent.planner import plan_question


@dataclass
class Plan:
    intent: str
    dataset: str
    metrics: List[str]
    filters: Dict[str, Any]


@dataclass
class ExecutionResult:
    sql: str
    rows: List[Dict[str, Any]]
    notes: List[str]
    status: str
    error_type: Optional[str]
    error_message: Optional[str]


def is_read_only(sql: str) -> bool:
    stripped = sql.strip().lower()
    stripped = stripped.rstrip(";").strip()
    if ";" in stripped:
        return False
    if not (stripped.startswith("select") or stripped.startswith("with")):
        return False
    blocked = ("drop ", "delete ", "update ", "insert ", "alter ", "truncate ", "create ")
    return not any(token in stripped for token in blocked)


def classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "syntax" in msg:
        return "SYNTAX_ERROR"
    if "timeout" in msg or "timed out" in msg:
        return "TIMEOUT"
    if "connection" in msg or "could not connect" in msg:
        return "CONNECTION"
    return "UNKNOWN"


def is_mask_target(column: str) -> bool:
    if column.endswith(("_pop", "_cnt", "_sum", "_num")):
        return True
    if re.fullmatch(r"(m|w)_(\d{4}|70u)", column):
        return True
    return False


def apply_pii_masking(rows: List[Dict[str, Any]], threshold: float = 5.0) -> List[Dict[str, Any]]:
    masked = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            try:
                num = float(str(value))
            except (TypeError, ValueError):
                new_row[key] = value
                continue
            if is_mask_target(key) and num < threshold:
                new_row[key] = "MASKED"
            else:
                new_row[key] = value
        masked.append(new_row)
    return masked


def executor(
    sql_payload: Dict[str, Any],
    execute_sql: Callable[[str], List[Dict[str, Any]]],
) -> ExecutionResult:
    sql = sql_payload["sql"]
    if not is_read_only(sql):
        raise ValueError("Only SELECT/CTE statements are allowed.")
    try:
        rows = execute_sql(sql)
        return ExecutionResult(
            sql=sql,
            rows=rows,
            notes=[],
            status="SUCCESS",
            error_type=None,
            error_message=None,
        )
    except Exception as exc:
        return ExecutionResult(
            sql=sql,
            rows=[],
            notes=[str(exc)],
            status="FAIL",
            error_type=classify_error(exc),
            error_message=str(exc),
        )


def checker(result: ExecutionResult) -> ExecutionResult:
    if not result.rows:
        result.notes.append("No rows returned.")
    return result


async def run_workflow(
    question: str,
    mapping_path: Path,
    plan_schema_path: Path,
    sql_schema_path: Path,
    execute_sql: Callable[[str], List[Dict[str, Any]]],
    client: LLMClient,
    debug: bool = False,
    knowledge_card_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    execution_log_hook: Optional[Callable[[ExecutionResult], None]] = None,
) -> ExecutionResult:
    plan, _ = await plan_question(question, mapping_path, plan_schema_path, client, debug=debug)
    sql_payload, _ = await plan_to_sql(plan, mapping_path, sql_schema_path, client, debug=debug)
    result = executor(sql_payload, execute_sql)
    if result.status == "SUCCESS":
        result.rows = apply_pii_masking(result.rows)
        if knowledge_card_hook:
            knowledge_card_hook(
                {
                    "title": question,
                    "tags": [],
                    "summary": f"Auto-generated for {question}.",
                    "sources": [plan.get("dataset", "")],
                }
            )
    if execution_log_hook:
        execution_log_hook(result)
    return checker(result)
