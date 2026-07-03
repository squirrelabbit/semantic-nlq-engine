import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.types.json import Json
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import yaml

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

logger = logging.getLogger("api_server")

from agent.coder import plan_to_sql
from agent.core import execute_mcp_sql, is_read_only, sanitize_rows, validate_sql_tables
from agent.llm_client import LLMClient
from agent.planner import plan_question, plan_question_two_stage
from semantic.metrics import load_metrics
from scripts.run_agent import apply_pii_mask, execute_direct_sql, log_execution, summarize_rows

# Database connection helper
def get_db_conn():
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        raise HTTPException(status_code=500, detail="Database environment variables are not set.")
    return psycopg.connect(f"dbname={db} user={user} password={password} host={host} port={port}")


def _normalize_json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _normalize_card(card: Dict[str, Any]) -> Dict[str, Any]:
    card["tags"] = _normalize_json_field(card.get("tags"))
    card["sources"] = _normalize_json_field(card.get("sources"))
    return card


def _normalize_rows_payload(rows: Any) -> Any:
    if isinstance(rows, dict) and "result" in rows:
        return rows["result"]
    return rows


def _fallback_summary(
    metric_semantics: Dict[str, Any],
    stats: Optional[Dict[str, Any]],
) -> str:
    if not stats or not isinstance(stats, dict):
        return "결과 없음"
    metrics_stats = stats.get("metrics", {})
    if not isinstance(metrics_stats, dict) or not metrics_stats:
        return "결과 없음"
    alias_map = {
        "h_pop": "total_h_pop",
        "w_pop": "total_w_pop",
        "v_pop": "total_v_pop",
    }
    metric_names = []
    for name in metric_semantics.keys():
        if name in metrics_stats:
            metric_names.append(name)
            continue
        alias = alias_map.get(name)
        if alias and alias in metrics_stats:
            metric_names.append(name)
    if not metric_names:
        return "결과 없음"

    core_metrics = []
    for name in metric_names[:3]:
        meta = metric_semantics.get(name, {})
        display = meta.get("display_name", name)
        value = None
        if name in metrics_stats:
            value = metrics_stats.get(name, {}).get("sum")
        else:
            alias = alias_map.get(name)
            if alias:
                value = metrics_stats.get(alias, {}).get("sum")
        if value is not None:
            core_metrics.append(f"{display} {value:,.0f}명")
    core_text = ", ".join(core_metrics) if core_metrics else "결과 없음"

    first_meta = metric_semantics.get(metric_names[0], {})
    domain_meaning = first_meta.get("domain_meaning", "")
    rules = first_meta.get("interpretation_rules", [])
    rule_text = rules[0] if rules else ""

    summary = (
        f"요약: 제공된 지표 기준으로 해당 일자 유입 인구가 집계되었습니다. "
        f"핵심 수치: {core_text}. "
        f"해석: {domain_meaning or '지표 정의에 따라 해석합니다.'} "
        f"유의사항: {rule_text or '해석 규칙을 준수합니다.'}"
    )
    return summary


async def _summarize_with_llm(
    client: LLMClient,
    question: str,
    sql: str,
    rows: Any,
    stats: Optional[Dict[str, Any]],
) -> Optional[str]:
    metric_semantics = load_metrics(repo_root / "semantics/metrics.yaml")
    allowed_metric_names = sorted(metric_semantics.keys())
    messages = [
        {
            "role": "system",
            "content": (
                "You are a policy data analyst. Summarize results in Korean using the fixed template below.\n"
                "\n"
                "[Fixed Template]\n"
                "1) 요약: 한 문장으로만 작성\n"
                "2) 핵심 수치: 제공된 지표만 나열 (최대 3개)\n"
                "3) 해석: metric semantics의 domain_meaning만 사용\n"
                "4) 유의사항: interpretation_rules에서 1개만 인용\n"
                "\n"
                "[Hard Rules]\n"
                "- 성별/연령을 추론하거나 언급하지 말 것\n"
                "- 정책 제언/권고/전략 문구 작성 금지\n"
                "- '의미 없음/무의미' 같은 평가 문구 금지\n"
                "- 표/목록 형태로 출력하지 말 것\n"
                "- 지표는 allowed_metrics 목록에 있는 것만 언급\n"
                "\n"
                "Use provided metric semantics verbatim. If no rows, state: '결과 없음'."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": question,
                    "sql": sql,
                    "rows": rows,
                    "insight": stats,
                    "metric_semantics": metric_semantics,
                    "allowed_metrics": allowed_metric_names,
                },
                ensure_ascii=False,
            ),
        },
    ]
    content, _, _ = await client.chat(messages)
    if content:
        return content.strip()
    logger.warning("LLM summary returned empty content.")
    return None

# Pydantic Models
class NLQRequest(BaseModel):
    question: str = Field(..., description="User question in natural language.")
    two_stage: bool = True
    execute: bool = True
    interpret: bool = False
    direct: bool = False
    interpret_always: bool = False
    use_mock: bool = False
    mock_data_ref: Optional[str] = None
    mock_planner_file: Optional[str] = None
    mock_coder_file: Optional[str] = None
    use_mock: bool = False
    mock_planner_file: Optional[str] = None
    mock_coder_file: Optional[str] = None
    mock_planner_file: Optional[str] = None
    mock_coder_file: Optional[str] = None


class NLQResponse(BaseModel):
    plan: Dict[str, Any]
    sql: Optional[str]
    rows: Optional[list[Dict[str, Any]]]
    insight: Optional[Dict[str, Any]]
    request_id: str


class KnowledgeCardCreate(BaseModel):
    title: str
    summary: str
    tags: Optional[List[str]] = []
    sources: Optional[List[str]] = []

class KnowledgeCard(KnowledgeCardCreate):
    id: int
    created_at: datetime


class SemanticMetadataCreate(BaseModel):
    target_table: str
    business_name: Optional[str] = None
    semantic_desc: Optional[str] = None
    join_rules: Optional[List[Dict[str, Any]]] = None
    allowed_metrics: Optional[List[str]] = None
    constraints: Optional[List[str]] = None
    samples: Optional[Dict[str, Any]] = None

class SemanticMetadata(SemanticMetadataCreate):
    id: int
    updated_at: datetime


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


def get_mapping_path() -> Path:
    mapping_path = os.getenv("POC_MAPPING_PATH")
    if mapping_path:
        return Path(mapping_path)
    if os.getenv("POC_MODE") in ("1", "true", "TRUE"):
        poc_path = repo_root / "semantic/semantic_mapping_poc.json"
        if poc_path.exists():
            return poc_path
    return repo_root / "semantic/semantic_mapping.json"


def load_poc_questions() -> list[str]:
    question_paths = [
        repo_root / "questions/daily.yaml",
        repo_root / "questions/deep_analysis.yaml",
    ]
    questions = []
    for path in question_paths:
        if not path.exists():
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for item in payload.get("questions", []):
            text = item.get("text")
            if text:
                questions.append(text)
    return questions


def is_risky_question(question: str) -> bool:
    lowered = question.lower()
    blocked_tokens = (
        "drop ",
        "delete ",
        "update ",
        "insert ",
        "alter ",
        "truncate ",
        "create ",
        "grant ",
        "revoke ",
    )
    if any(token in lowered for token in blocked_tokens):
        return True
    return False


app = FastAPI(title="Ontology NLQ API", version="0.1.0")
load_dotenv(repo_root / ".env")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/report/latest")
def get_latest_report() -> Dict[str, Any]:
    reports_dir = repo_root / "reports"
    if not reports_dir.exists():
        raise HTTPException(status_code=404, detail="reports directory not found.")
    reports = sorted(reports_dir.glob("daily_report_*.json"))
    if not reports:
        raise HTTPException(status_code=404, detail="No daily reports found.")
    latest_report = reports[-1]
    return json.loads(latest_report.read_text(encoding="utf-8"))


@app.get("/api/mock_scenarios")
def get_mock_scenarios() -> List[Dict[str, Any]]:
    primary_path = repo_root / "questions/mock_scenarios.json"
    fallback_path = repo_root / "questions/mock_scenarios_v2.json"
    scenarios_path = primary_path if primary_path.exists() else fallback_path
    if not scenarios_path.exists():
        return []
    return json.loads(scenarios_path.read_text(encoding="utf-8"))



@app.post("/api/nlq", response_model=NLQResponse)
async def nlq(request: NLQRequest) -> NLQResponse:
    if is_risky_question(request.question):
        raise HTTPException(
            status_code=400,
            detail="위험한 요청으로 판단되어 차단되었습니다.",
        )
    if os.getenv("POC_MODE") in ("1", "true", "TRUE"):
        allowed = load_poc_questions()
        if allowed and request.question not in allowed:
            raise HTTPException(status_code=400, detail="PoC 질문 세트에 포함되지 않은 질의입니다.")

    plan: Dict[str, Any]
    sql: Optional[str]

    if request.use_mock:
        mock_payload: Dict[str, Any] = {}
        if request.mock_data_ref:
            mock_path = repo_root / request.mock_data_ref
            if not mock_path.exists():
                raise HTTPException(status_code=500, detail="Mock data file not found.")
            mock_payload = json.loads(mock_path.read_text(encoding="utf-8"))
        else:
            try:
                planner_filename = request.mock_planner_file or "mock_planner_response.json"
                coder_filename = request.mock_coder_file or "mock_coder_response.json"
                mock_payload["plan"] = json.loads((repo_root / planner_filename).read_text(encoding="utf-8"))
                sql_payload = json.loads((repo_root / coder_filename).read_text(encoding="utf-8"))
                mock_payload["sql"] = sql_payload.get("sql")
            except FileNotFoundError as exc:
                raise HTTPException(status_code=500, detail="Mock response files not found.") from exc

        plan = mock_payload.get("plan", {})
        sql = mock_payload.get("sql")
        rows = mock_payload.get("rows")
        insight = mock_payload.get("insight")
        request_id = str(uuid.uuid4())
        return NLQResponse(plan=plan, sql=sql, rows=rows, insight=insight, request_id=request_id)

    else:
        # Original LLM call logic
        client = LLMClient()
        if request.two_stage:
            plan, _ = await plan_question_two_stage(
                request.question,
                get_mapping_path(),
                repo_root / "agent/plan_l1_schema.json",
                repo_root / "agent/plan_schema.json",
                client,
                debug=False,
            )
        else:
            plan, _ = await plan_question(
                request.question,
                get_mapping_path(),
                repo_root / "agent/plan_schema.json",
                client,
                debug=False,
            )

        sql_payload, _ = await plan_to_sql(
            plan,
            get_mapping_path(),
            repo_root / "agent/sql_schema.json",
            client,
            debug=False,
        )
        sql = sql_payload.get("sql") if isinstance(sql_payload, dict) else None

    if not sql:
        raise HTTPException(status_code=400, detail="Failed to generate SQL.")
    if not is_read_only(sql):
        raise HTTPException(status_code=400, detail="Only SELECT/CTE statements are allowed.")
    try:
        validate_sql_tables(sql, get_mapping_path())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    request_id = str(uuid.uuid4())
    rows: Any = None
    insight = None
    if request.execute:
        start = time.perf_counter()
        try:
            if request.direct:
                if os.getenv("ALLOW_DIRECT_SQL") not in ("1", "true", "TRUE"):
                    raise HTTPException(
                        status_code=400,
                        detail="Direct SQL execution is disabled. Use MCP execution.",
                    )
                rows = execute_direct_sql(sql)
            else:
                rows = await execute_mcp_sql(sql, repo_root)
            
            rows = _normalize_rows_payload(rows)
            rows = sanitize_rows(apply_pii_mask(rows))
            log_execution(request_id, request.question, sql, time.perf_counter() - start, "SUCCESS", None)
        except Exception as exc:
            log_execution(request_id, request.question, sql, time.perf_counter() - start, "FAIL", str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        
        if request.interpret or request.interpret_always:
            stats = summarize_rows(rows)
            metric_semantics = load_metrics(repo_root / "semantics/metrics.yaml")
            insight = {"stats": stats}
            if request.interpret_always:
                client = LLMClient()
                llm_summary = await _summarize_with_llm(client, request.question, sql, rows, stats)
                insight["summary"] = llm_summary or _fallback_summary(metric_semantics, stats)

    return NLQResponse(plan=plan, sql=sql, rows=rows, insight=insight, request_id=request_id)

# --- Knowledge Card CRUD Endpoints ---

@app.post("/api/knowledge_cards", response_model=KnowledgeCard, status_code=status.HTTP_201_CREATED)
def create_knowledge_card(card: KnowledgeCardCreate):
    with get_db_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                INSERT INTO knowledge_cards (title, summary, tags, sources)
                VALUES (%s, %s, %s, %s)
                RETURNING id, title, summary, tags, sources, created_at
                """,
                (card.title, card.summary, Json(card.tags), Json(card.sources)),
            )
            new_card = cur.fetchone()
            conn.commit()
            if not new_card:
                raise HTTPException(status_code=500, detail="Failed to create knowledge card.")
            return _normalize_card(dict(new_card))

@app.get("/api/knowledge_cards", response_model=List[KnowledgeCard])
def list_knowledge_cards():
    with get_db_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT id, title, summary, tags, sources, created_at FROM knowledge_cards ORDER BY created_at DESC")
            cards = cur.fetchall()
            return [_normalize_card(dict(card)) for card in cards]

@app.get("/api/knowledge_cards/{card_id}", response_model=KnowledgeCard)
def get_knowledge_card(card_id: int):
    with get_db_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT id, title, summary, tags, sources, created_at FROM knowledge_cards WHERE id = %s", (card_id,))
            card = cur.fetchone()
            if not card:
                raise HTTPException(status_code=404, detail="Knowledge card not found.")
            return _normalize_card(dict(card))

@app.put("/api/knowledge_cards/{card_id}", response_model=KnowledgeCard)
def update_knowledge_card(card_id: int, card: KnowledgeCardCreate):
    with get_db_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                UPDATE knowledge_cards
                SET title = %s, summary = %s, tags = %s, sources = %s
                WHERE id = %s
                RETURNING id, title, summary, tags, sources, created_at
                """,
                (card.title, card.summary, Json(card.tags), Json(card.sources), card_id),
            )
            updated_card = cur.fetchone()
            conn.commit()
            if not updated_card:
                raise HTTPException(status_code=404, detail="Knowledge card not found.")
            return _normalize_card(dict(updated_card))

@app.delete("/api/knowledge_cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_card(card_id: int):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_cards WHERE id = %s", (card_id,))
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Knowledge card not found.")
    return

# --- Semantic Metadata CRUD Endpoints ---

@app.post("/api/semantic_metadata", response_model=SemanticMetadata, status_code=status.HTTP_201_CREATED)
def create_semantic_metadata(meta: SemanticMetadataCreate):
    # Since target_table is unique, handle potential conflict
    sql = """
        INSERT INTO semantic_metadata (target_table, business_name, semantic_desc, join_rules, allowed_metrics, constraints, samples)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (target_table) DO NOTHING
        RETURNING id, target_table, business_name, semantic_desc, join_rules, allowed_metrics, constraints, samples, updated_at
    """
    with get_db_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            try:
                cur.execute(
                    sql,
                    (
                        meta.target_table,
                        meta.business_name,
                        meta.semantic_desc,
                        Json(meta.join_rules),
                        Json(meta.allowed_metrics),
                        Json(meta.constraints),
                        Json(meta.samples),
                    ),
                )
                new_meta = cur.fetchone()
                conn.commit()
                if not new_meta:
                    raise HTTPException(status_code=409, detail=f"Semantic metadata for table '{meta.target_table}' already exists.")
                return new_meta
            except psycopg.Error as e:
                 raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.get("/api/semantic_metadata", response_model=List[SemanticMetadata])
def list_semantic_metadata():
    with get_db_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""
                SELECT id, target_table, business_name, semantic_desc, join_rules, allowed_metrics, constraints, samples, updated_at
                FROM semantic_metadata ORDER BY target_table
            """)
            metadata = cur.fetchall()
            return metadata

@app.get("/api/semantic_metadata/{meta_id}", response_model=SemanticMetadata)
def get_semantic_metadata(meta_id: int):
    with get_db_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""
                SELECT id, target_table, business_name, semantic_desc, join_rules, allowed_metrics, constraints, samples, updated_at
                FROM semantic_metadata WHERE id = %s
            """, (meta_id,))
            meta = cur.fetchone()
            if not meta:
                raise HTTPException(status_code=404, detail="Semantic metadata not found.")
            return meta

@app.put("/api/semantic_metadata/{meta_id}", response_model=SemanticMetadata)
def update_semantic_metadata(meta_id: int, meta: SemanticMetadataCreate):
    sql = """
        UPDATE semantic_metadata
        SET target_table = %s, business_name = %s, semantic_desc = %s, join_rules = %s,
            allowed_metrics = %s, constraints = %s, samples = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, target_table, business_name, semantic_desc, join_rules, allowed_metrics, constraints, samples, updated_at
    """
    with get_db_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            try:
                cur.execute(
                    sql,
                    (
                        meta.target_table,
                        meta.business_name,
                        meta.semantic_desc,
                        Json(meta.join_rules),
                        Json(meta.allowed_metrics),
                        Json(meta.constraints),
                        Json(meta.samples),
                        meta_id,
                    ),
                )
                updated_meta = cur.fetchone()
                conn.commit()
                if not updated_meta:
                    raise HTTPException(status_code=404, detail="Semantic metadata not found.")
                return updated_meta
            except psycopg.Error as e:
                 raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.delete("/api/semantic_metadata/{meta_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_semantic_metadata(meta_id: int):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM semantic_metadata WHERE id = %s", (meta_id,))
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Semantic metadata not found.")
    return
