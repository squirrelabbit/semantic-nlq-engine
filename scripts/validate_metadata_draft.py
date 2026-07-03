import argparse
import json
import os
import sys
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


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


def build_schema_maps(schema: dict[str, object]) -> tuple[set[str], dict[str, set[str]]]:
    tables = {t["table_name"] for t in schema.get("tables", []) if t.get("table_schema") == "public"}
    columns: dict[str, set[str]] = {}
    for col in schema.get("columns", []):
        if col.get("table_schema") != "public":
            continue
        table = col.get("table_name")
        name = col.get("column_name")
        if not table or not name:
            continue
        columns.setdefault(table, set()).add(name)
    return tables, columns


def validate_draft(draft: dict[str, object], tables: set[str], columns: dict[str, set[str]]) -> list[str]:
    issues: list[str] = []
    for dataset in draft.get("datasets", []):
        table = dataset.get("table")
        if not table:
            issues.append("Dataset missing table name.")
            continue
        if table not in tables:
            issues.append(f"Unknown table: {table}")
            continue

        for col in dataset.get("columns", []):
            name = col.get("name")
            if not name:
                issues.append(f"{table}: column missing name.")
                continue
            if name not in columns.get(table, set()):
                issues.append(f"{table}.{name} not found in DB schema.")
    return issues


async def run() -> None:
    parser = argparse.ArgumentParser(description="Validate metadata_draft.json against DB schema.")
    parser.add_argument("--draft", default="ontology/metadata_draft.json")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server/main.py"],
        env=build_env(),
        cwd=repo_root,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("inspect_db")
            schema = result.structuredContent if result.structuredContent is not None else result.content

    normalized = normalize_schema(schema)
    tables, columns = build_schema_maps(normalized)

    draft_path = repo_root / args.draft
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    issues = validate_draft(draft, tables, columns)

    if issues:
        print("Validation issues:")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)

    print("Validation OK.")


if __name__ == "__main__":
    anyio.run(run)
