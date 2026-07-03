import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Tuple

from agent.llm_client import LLMClient
from agent.llm_parser import extract_json
from semantic.metrics import format_metric_context, load_metrics
from semantic.prompt_builder import build_dynamic_context, build_l1_context, build_l2_context
from semantic.semantic_layer import load_mapping


def build_plan_request(
    question: str,
    mapping_path: Path,
    schema_path: Path,
    selected_tables: list[str] | None = None,
) -> Dict[str, Any]:
    mapping = load_mapping(mapping_path)
    metrics_path = mapping_path.parents[1] / "semantics/metrics.yaml"
    metric_semantics = load_metrics(metrics_path)
    if selected_tables is None:
        context = build_l1_context(mapping)
    else:
        context = build_l2_context(mapping, selected_tables)
        metric_context = format_metric_context(metric_semantics)
        if metric_context:
            context = (
                f"{context}\n\n{metric_context}\n"
                "Use only the metrics listed above. Do not infer gender/age meanings from metric names."
            )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    current_date = date.today().isoformat()

    system_prompt = (
        "You are an NLQ planner. Extract intent, dataset, metrics, filters, and group_by as JSON. "
        "Use dataset names exactly as listed. If the question includes a place, "
        "set filters.place_name. Intent must be one of SEARCH, TREND, COMPARISON, RANKING. "
        "If the question asks for a breakdown (e.g., 성별/연령별/지역별/시간대별), "
        "include group_by with the relevant columns. "
        "group_by must use only columns listed for the chosen dataset (never invent). "
        "If the requested breakdown is not available in the chosen dataset, "
        "switch to a dataset that has the needed columns or leave group_by empty "
        "and add a note. "
        "If the question implies a date range (e.g., 지난주/최근 3일), include time_range "
        "with start/end as YYYYMMDD. Always include original_question and confidence (0-1). "
        "Return JSON only."
    )
    if selected_tables is None:
        system_prompt = (
            "You are an NLQ planner. Select the single best dataset (table name) to answer the question. "
            "Return JSON only with the key 'dataset' (string) and 'original_question'. "
            "Do not invent dataset names. Do not provide rankings or multiple datasets."
        )
    else:
        system_prompt = (
            "You are an NLQ planner. Choose exactly one dataset from the candidates and finalize the plan. "
            "Use dataset names exactly as listed. If the question includes a place, "
            "set filters.place_name. Intent must be one of SEARCH, TREND, COMPARISON, RANKING. "
            "If Intent is SEARCH and the question implies a summary (e.g., '요약해줘'), "
            "you MUST select 'h_pop', 'w_pop', and 'v_pop' as metrics if they are available in the chosen dataset. "
            "If the question asks for a breakdown (e.g., 성별/연령별/지역별/시간대별), "
            "include group_by with the relevant columns. "
            "group_by must use only columns listed for the chosen dataset (never invent). "
            "If the requested breakdown is not available in the chosen dataset, "
            "switch to a dataset that has the needed columns or leave group_by empty "
            "and add a note. "
            "If the question implies a date range (e.g., 지난주/최근 3일), include time_range "
            "with start/end as YYYYMMDD. Always include original_question and confidence (0-1). "
            "Return JSON only."
        )

    return {
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": (
                    f"{context}\n\nCurrent_Date: {current_date}\n"
                    f"Question: {question}\n\nSchema:\n{json.dumps(schema)}"
                ),
            },
        ]
    }


def _enforce_known_metrics(
    plan: Dict[str, Any],
    metric_semantics: Dict[str, Any],
) -> Dict[str, Any]:
    if not metric_semantics:
        return plan
    allowed = set(metric_semantics.keys())
    metrics = [m for m in plan.get("metrics", []) if m in allowed]
    if metrics != plan.get("metrics", []):
        plan["metrics"] = metrics
        note = plan.get("notes", "")
        suffix = "Removed metrics not defined in semantics/metrics.yaml."
        plan["notes"] = f"{note} {suffix}".strip()
    return plan


async def plan_question(
    question: str,
    mapping_path: Path,
    schema_path: Path,
    client: LLMClient,
    debug: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    request_payload = build_plan_request(question, mapping_path, schema_path, selected_tables=[])
    content, request_payload, response_payload = await client.chat(
        request_payload["messages"],
        temperature=0,
        response_format={"type": "json_object"},
    )
    parsed, error = extract_json(content)
    if not parsed:
        parsed = {
            "intent": "SEARCH",
            "dataset": "",
            "metrics": [],
            "filters": {},
            "notes": error or "Failed to parse LLM response.",
        }

    metric_semantics = load_metrics(mapping_path.parents[1] / "semantics/metrics.yaml")
    parsed.setdefault("original_question", question)
    parsed = _enforce_known_metrics(parsed, metric_semantics)
    debug_payload = {"llm_request": request_payload, "llm_response": response_payload}
    if debug:
        debug_payload["llm_raw"] = content
    return parsed, debug_payload


async def plan_question_two_stage(
    question: str,
    mapping_path: Path,
    l1_schema_path: Path,
    l2_schema_path: Path,
    client: LLMClient,
    debug: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    l1_request = build_plan_request(question, mapping_path, l1_schema_path, selected_tables=None)
    l1_content, l1_request, l1_response = await client.chat(
        l1_request["messages"],
        temperature=0,
        response_format={"type": "json_object"},
    )
    l1_parsed, l1_error = extract_json(l1_content)

    # NEW: Extract single dataset name from L1
    selected_l1_dataset_name = l1_parsed.get("dataset") if isinstance(l1_parsed, dict) else ""
    
    # Pass the selected dataset name (as a list for the `selected_tables` parameter)
    l2_request = build_plan_request(
        question,
        mapping_path,
        l2_schema_path,
        selected_tables=[selected_l1_dataset_name] if selected_l1_dataset_name else []
    )
    l2_content, l2_request, l2_response = await client.chat(
        l2_request["messages"],
        temperature=0,
        response_format={"type": "json_object"},
    )
    l2_parsed, l2_error = extract_json(l2_content)
    if not l2_parsed:
        l2_parsed = {
            "intent": "SEARCH",
            "dataset": selected_l1_dataset_name if selected_l1_dataset_name else "", # Use L1's choice as fallback
            "metrics": [],
            "filters": {},
            "notes": l2_error or "Failed to parse LLM response.",
        }

    metric_semantics = load_metrics(mapping_path.parents[1] / "semantics/metrics.yaml")
    l2_parsed.setdefault("original_question", question)
    l2_parsed = _enforce_known_metrics(l2_parsed, metric_semantics)
    debug_payload = {
        "l1_request": l1_request,
        "l1_response": l1_response,
        "l1_raw": l1_content if debug else None,
        "l1_error": l1_error,
        "l2_request": l2_request,
        "l2_response": l2_response,
        "l2_raw": l2_content if debug else None,
        "l2_error": l2_error,
    }
    return l2_parsed, debug_payload
