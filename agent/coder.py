import json
from pathlib import Path
from typing import Any, Dict, Tuple

from agent.llm_client import LLMClient
from agent.llm_parser import extract_json
from semantic.semantic_layer import dataset_columns, get_dataset, load_mapping


def build_sql_request(plan: Dict[str, Any], mapping_path: Path, schema_path: Path) -> Dict[str, Any]:
    mapping = load_mapping(mapping_path)
    dataset_name = plan.get("dataset", "")
    dataset = get_dataset(mapping, dataset_name) if dataset_name else None
    if not dataset:
        return {
            "error": f"Unknown dataset: {dataset_name}",
            "messages": [],
        }

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    columns = dataset_columns(dataset)
    joins = dataset.get("joins", [])

    join_lines = []
    for join in joins:
        column = join.get("column")
        ref_table = join.get("ref_table")
        ref_column = join.get("ref_column")
        ref_name = join.get("ref_name")
        description = join.get("description")
        sql_hint = join.get("sql_hint")
        if column and ref_table and ref_column:
            detail = f"{column} -> {ref_table}.{ref_column}"
            if ref_name:
                detail += f" (name: {ref_table}.{ref_name})"
            if description:
                detail += f" (hint: {description})"
            if sql_hint:
                detail += f" (sql: {sql_hint})"
            join_lines.append(detail)

    join_section = ""
    if join_lines:
        join_section = "Join hints:\n- " + "\n- ".join(join_lines)

    constraint_hints = build_constraint_hints(plan, mapping, dataset)
    constraint_section = ""
    if constraint_hints:
        constraint_section = "Constraints:\n- " + "\n- ".join(constraint_hints)

    original_question = plan.get("original_question")
    question_line = f"Original question: {original_question}\n" if original_question else ""
    place_hint = (
        "Place name rule: treat place_name as destination (hcode) by default. "
        "Use inflow_cd only when the question explicitly refers to origin/inflow area. "
        "When matching a city/region name, prefer LIKE (e.g., name LIKE '%성남시%') over strict equality.\n"
    )
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert SQL generator for PostgreSQL. "
                    "Your MOST IMPORTANT rule is to generate simple, flat, table-based SELECT queries.\n"
                    "- **DO NOT USE**: `JSON_AGG`, `JSON_BUILD_OBJECT`, `->`, `->>`.\n"
                    "- **ALWAYS DO**: `SELECT column1, column2, SUM(column3) FROM ... GROUP BY ...`\n"
                    "- The query MUST return multiple rows and columns, NOT a single JSON string.\n"
                    "- Ensure all parentheses are correctly matched.\n"
                    "- Return a single JSON object with the key 'sql'."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{question_line}"
                    f"{place_hint}"
                    f"Dataset: {dataset_name}\n"
                    f"Columns: {', '.join(columns)}\n"
                f"{join_section}\n"
                f"{constraint_section}\n\n"
                    f"Plan JSON:\n{json.dumps(plan, ensure_ascii=True)}\n\n"
                    f"Return SQL as JSON only. Schema:\n{json.dumps(schema)}"
                ),
            },
        ]
    }


async def plan_to_sql(
    plan: Dict[str, Any],
    mapping_path: Path,
    schema_path: Path,
    client: LLMClient,
    debug: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    request_payload = build_sql_request(plan, mapping_path, schema_path)
    if request_payload.get("error"):
        return {"sql": "", "notes": request_payload["error"]}, {"llm_request": {}, "llm_response": {}}

    content, request_payload, response_payload = await client.chat(
        request_payload["messages"],
        temperature=0,
        response_format={"type": "json_object"},
        max_tokens=600,
    )
    parsed, error = extract_json(content)
    if not parsed or not parsed.get("sql"):
        parsed = {
            "sql": "",
            "notes": error or "Failed to generate SQL.",
        }

    debug_payload = {"llm_request": request_payload, "llm_response": response_payload}
    if debug:
        debug_payload["llm_raw"] = content
    return parsed, debug_payload


def build_constraint_hints(plan: Dict[str, Any], mapping: dict, dataset: dict) -> list[str]:
    hints: list[str] = []
    std_ymd = plan.get("filters", {}).get("std_ymd")

    # Add constraints directly from the current dataset
    for rule in dataset.get("constraints", []):
        if "{std_ymd}" in rule and std_ymd:
            hints.append(rule.format(std_ymd=std_ymd))
        else:
            hints.append(rule)

    # Then, iterate over joins (original logic)
    for join in dataset.get("joins", []):
        if join.get("ref_table") != "place_codes":
            continue
        place_codes = get_dataset(mapping, "place_codes")
        if not place_codes:
            continue
        for rule in place_codes.get("constraints", []):
            if "{std_ymd}" in rule and std_ymd:
                hints.append(rule.format(std_ymd=std_ymd))
            else:
                hints.append(rule)
    return hints
