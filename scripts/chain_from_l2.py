import argparse
import json
import sys
import time
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from agent.coder import build_sql_request
from scripts.run_agent import apply_pii_mask, build_env, execute_direct_sql, log_execution, summarize_rows


def print_json(label: str, payload: object) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=True, indent=2, default=str)}")


async def run() -> None:
    parser = argparse.ArgumentParser(description="Chain L2 planner response to coder and execution.")
    parser.add_argument("--planner-response", required=True, help="L2 planner response JSON.")
    parser.add_argument("--coder-response", help="Coder response JSON (with sql).")
    parser.add_argument("--coder-messages-out", default="coder_messages.json")
    parser.add_argument("--mapping", default="semantic/semantic_mapping.json")
    parser.add_argument("--sql-schema", default="agent/sql_schema.json")
    parser.add_argument("--direct", action="store_true", help="Execute SQL directly (bypass MCP).")
    parser.add_argument("--interpret", action="store_true", help="Summarize rows after execution.")
    parser.add_argument("--auto", action="store_true", help="Enable interpret + default outputs.")
    parser.add_argument("--dump-output", help="Write sql/rows/insight payload to this JSON file.")
    parser.add_argument("--interpret-prompt-out", help="Write LLM prompt for interpreting results.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    plan_payload = json.loads(Path(args.planner_response).read_text(encoding="utf-8"))
    if not isinstance(plan_payload, dict) or not plan_payload.get("dataset"):
        raise SystemExit("planner-response must be an L2 response with dataset.")

    coder_payload = build_sql_request(plan_payload, repo_root / args.mapping, repo_root / args.sql_schema)
    Path(args.coder_messages_out).write_text(
        json.dumps(coder_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print_json("coder_messages", coder_payload)

    if not args.coder_response:
        return

    sql_payload = json.loads(Path(args.coder_response).read_text(encoding="utf-8"))
    sql = sql_payload.get("sql")
    if not sql:
        raise SystemExit("coder-response must contain a non-empty 'sql'.")
    sql = str(sql).lstrip("\ufeff").strip().rstrip(";")
    print_json("sql", sql)

    interpret = args.interpret or args.auto
    dump_output = args.dump_output or ("result_payload.json" if args.auto else None)
    interpret_prompt_out = args.interpret_prompt_out or ("interpret_prompt.json" if args.auto else None)

    if args.direct:
        start = time.perf_counter()
        request_id = f"chain-{int(start)}"
        try:
            rows = execute_direct_sql(sql)
            rows = apply_pii_mask(rows)
            print_json("rows", rows)
            log_execution(request_id, plan_payload.get("original_question", ""), sql, time.perf_counter() - start, "SUCCESS", None)
        except Exception as exc:  # pragma: no cover - execution guard
            log_execution(request_id, plan_payload.get("original_question", ""), sql, time.perf_counter() - start, "FAIL", str(exc))
            raise
        insight = summarize_rows(rows) if interpret else None
        if insight is not None:
            print_json("insight", insight)
        if dump_output:
            Path(dump_output).write_text(
                json.dumps({"sql": sql, "rows": rows, "insight": insight}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if interpret_prompt_out:
            question_value = plan_payload.get("original_question")
            prompt = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a policy data analyst. Summarize results in Korean. "
                            "Include: (1) one-sentence overview, (2) top 5 groups by the largest numeric metric, "
                            "(3) explain what each metric column represents, (4) one policy suggestion. "
                            "If no rows, explain possible reasons."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"question": question_value, "sql": sql, "rows": rows, "insight": insight},
                            ensure_ascii=False,
                        ),
                    },
                ]
            }
            Path(interpret_prompt_out).write_text(
                json.dumps(prompt, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server/main.py"],
        env=build_env(),
        cwd=repo_root,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            start = time.perf_counter()
            request_id = f"chain-{int(start)}"
            try:
                result = await session.call_tool("query_executor", {"sql": sql})
                rows = result.structuredContent if result.structuredContent is not None else result.content
                rows = apply_pii_mask(rows)
                print_json("rows", rows)
                log_execution(request_id, plan_payload.get("original_question", ""), sql, time.perf_counter() - start, "SUCCESS", None)
            except Exception as exc:  # pragma: no cover - execution guard
                log_execution(request_id, plan_payload.get("original_question", ""), sql, time.perf_counter() - start, "FAIL", str(exc))
                raise
            insight = summarize_rows(rows) if interpret else None
            if insight is not None:
                print_json("insight", insight)
            if dump_output:
                Path(dump_output).write_text(
                    json.dumps({"sql": sql, "rows": rows, "insight": insight}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            if interpret_prompt_out:
                question_value = plan_payload.get("original_question")
                prompt = {
                    "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a policy data analyst. Summarize results in Korean. "
                            "Include: (1) one-sentence overview, (2) top 5 groups by the largest numeric metric, "
                            "(3) explain what each metric column represents, (4) one policy suggestion. "
                            "If no rows, explain possible reasons."
                        ),
                    },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {"question": question_value, "sql": sql, "rows": rows, "insight": insight},
                                ensure_ascii=False,
                            ),
                        },
                    ]
                }
                Path(interpret_prompt_out).write_text(
                    json.dumps(prompt, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )


if __name__ == "__main__":
    anyio.run(run)
