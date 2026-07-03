import argparse
import json
import os
import sys
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from agent.llm_client import LLMClient
from agent.llm_parser import extract_json


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


def normalize_schema(schema: object) -> dict[str, object]:
    if isinstance(schema, dict) and "result" in schema and isinstance(schema["result"], dict):
        return schema["result"]
    if isinstance(schema, dict):
        return schema
    return {}


def build_schema_payload(
    schema: dict[str, object],
    sample_values: dict[str, dict[str, object]],
    joins: dict[str, list[dict[str, str]]],
) -> str:
    tables = schema.get("tables", [])
    columns = schema.get("columns", [])
    summary = {"tables": tables, "columns": columns, "samples": sample_values, "joins": joins}
    return json.dumps(summary, ensure_ascii=True)


def build_request(schema_payload: str) -> dict[str, object]:
    output_schema = {
        "type": "object",
        "required": ["datasets"],
        "additionalProperties": False,
        "properties": {
            "datasets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["table", "description", "columns"],
                    "additionalProperties": False,
                    "properties": {
                        "table": {"type": "string"},
                        "description": {"type": "string"},
                        "joins": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["column", "ref_table", "ref_column"],
                                "additionalProperties": False,
                                "properties": {
                                    "column": {"type": "string"},
                                    "ref_table": {"type": "string"},
                                    "ref_column": {"type": "string"},
                                    "ref_name": {"type": "string"},
                                },
                            },
                        },
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["name", "type", "role", "tags"],
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                    "role": {
                                        "type": "string",
                                        "description": "dimension or measure",
                                    },
                                    "tags": {"type": "array", "items": {"type": "string"}},
                                    "sample_value": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        },
    }

    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You generate a metadata draft from DB schema. "
                    "Output JSON only using the provided schema. "
                    "Use sample values to describe formats (e.g., 20231231 vs 2023-12-31). "
                    "Include join key hints when provided. "
                    "Every column must include role and tags; never leave them empty. "
                    "If unsure, set role to dimension and add tag #기타. "
                    "Add short Korean descriptions and semantic tags like "
                    "#시간, #지역, #인구, #성별, #연령, #좌표 when applicable."
                ),
            },
            {
                "role": "user",
                "content": (
                    "DB schema:\n"
                    f"{schema_payload}\n\n"
                    "Return metadata draft JSON.\n"
                    f"Schema:\n{json.dumps(output_schema, ensure_ascii=True)}"
                ),
            },
        ]
    }


def validate_metadata(parsed: dict) -> list[str]:
    issues: list[str] = []
    for dataset in parsed.get("datasets", []):
        table = dataset.get("table", "unknown")
        for col in dataset.get("columns", []):
            name = col.get("name", "unknown")
            role = col.get("role")
            tags = col.get("tags")
            if not role:
                issues.append(f"{table}.{name}: missing role")
            if not tags:
                issues.append(f"{table}.{name}: missing tags")
    return issues


async def run() -> None:
    parser = argparse.ArgumentParser(description="Generate metadata draft via LLM.")
    parser.add_argument("--output", default="ontology/metadata_draft.json")
    parser.add_argument("--llm-dump", help="Write LLM request payload to this JSON file and exit.")
    parser.add_argument("--llm-dump-out", help="Write LLM request payload to this JSON file and continue.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server/main.py"],
        env=build_env(),
        cwd=repo_root,
    )

    sample_values: dict[str, dict[str, object]] = {}
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("inspect_db")
            schema = result.structuredContent if result.structuredContent is not None else result.content
            normalized = normalize_schema(schema)
            tables = [
                t.get("table_name")
                for t in normalized.get("tables", [])
                if t.get("table_schema") == "public"
            ]
            for table in tables:
                if not table:
                    continue
                sample = await session.call_tool("get_sample_data", {"table": table, "limit": 1})
                rows = sample.structuredContent if sample.structuredContent is not None else sample.content
                row = {}
                if isinstance(rows, list) and rows:
                    row = rows[0]
                elif isinstance(rows, dict):
                    row = rows
                sample_values[table] = {k: row.get(k) for k in row}

    normalized = normalize_schema(schema)
    if not normalized.get("tables") or not normalized.get("columns"):
        raise SystemExit("inspect_db returned empty schema. Check MCP connection/env.")
    mapping_path = repo_root / "semantic/semantic_mapping.json"
    joins: dict[str, list[dict[str, str]]] = {}
    if mapping_path.exists():
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        for dataset in mapping.get("datasets", []):
            table = dataset.get("table")
            if table and dataset.get("joins"):
                joins[table] = dataset.get("joins")

    schema_payload = build_schema_payload(normalized, sample_values, joins)
    request_payload = build_request(schema_payload)

    if args.llm_dump:
        Path(args.llm_dump).write_text(
            json.dumps(request_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Wrote LLM request payload to {args.llm_dump}")
        return
    if args.llm_dump_out:
        Path(args.llm_dump_out).write_text(
            json.dumps(request_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Wrote LLM request payload to {args.llm_dump_out}")

    client = LLMClient()
    content, _, _ = await client.chat(request_payload["messages"])
    parsed, error = extract_json(content)
    if not parsed:
        raise SystemExit(error or "Failed to parse LLM response.")
    issues = validate_metadata(parsed)
    if issues:
        joined = "\n".join(f"- {item}" for item in issues)
        raise SystemExit(f"Metadata validation failed:\n{joined}")

    output_path = repo_root / args.output
    output_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote metadata draft to {output_path}")


if __name__ == "__main__":
    anyio.run(run)
