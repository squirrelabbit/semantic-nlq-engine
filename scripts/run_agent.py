import argparse
import json
import os
import sys
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from agent.coder import build_sql_request, plan_to_sql
from agent.core import (
    apply_pii_mask,
    execute_direct_sql,
    log_execution,
    run_nlq_workflow,
    sanitize_rows,
    summarize_rows,
    validate_sql_tables,
)
from agent.llm_client import LLMClient
from agent.planner import build_plan_request, plan_question, plan_question_two_stage
from semantic.metrics import load_metrics


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


def print_json(label: str, payload: object) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=True, indent=2, default=str)}")


def load_metric_semantics(repo_root: Path) -> dict:
    return load_metrics(repo_root / "semantics/metrics.yaml")


async def run() -> None:
    parser = argparse.ArgumentParser(description="Run NLQ agent workflow over MCP.")
    parser.add_argument("question", help="User question in natural language.")
    parser.add_argument("--mapping", default="semantic/semantic_mapping.json")
    parser.add_argument("--plan-schema", default="agent/plan_schema.json")
    parser.add_argument("--plan-l1-schema", default="agent/plan_l1_schema.json")
    parser.add_argument("--sql-schema", default="agent/sql_schema.json")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--llm-dump", help="Write LLM request payloads to this JSON file and exit.")
    parser.add_argument("--llm-log", help="Write LLM request/response payloads to this JSON file.")
    parser.add_argument("--plan-json", help="Plan JSON file to build the SQL planner request.")
    parser.add_argument("--sql-json", help="SQL JSON file (with sql field) for manual run.")
    parser.add_argument("--manual-run", action="store_true", help="Execute SQL from --sql-json via MCP.")
    parser.add_argument("--interpret", action="store_true", help="Summarize rows after execution.")
    parser.add_argument("--dump-output", help="Write sql/rows/insight payload to this JSON file.")
    parser.add_argument("--direct", action="store_true", help="Execute SQL directly (bypass MCP).")
    parser.add_argument("--interpret-prompt-out", help="Write LLM prompt for interpreting results.")
    parser.add_argument("--two-stage", action="store_true", help="Use L1/L2 two-stage planner flow.")
    parser.add_argument(
        "--planner-response-out",
        help="Write derived planner or coder messages to this JSON file.",
    )
    parser.add_argument(
        "--auto-next",
        action="store_true",
        help="Write next-step payloads to default files when --planner-response is used.",
    )
    parser.add_argument(
        "--planner-response",
        help="Planner JSON response file to generate coder LLM messages.",
    )
    parser.add_argument(
        "--coder-response",
        help="Coder JSON response file (with sql field) to execute via MCP.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    try:
        import psycopg  # noqa: F401
    except Exception as exc:  # pragma: no cover - env guard
        raise SystemExit(
            "psycopg is required for the MCP server. Run: pip install -r requirements.txt"
        ) from exc

    # Note: all manual/debug flows are preserved as-is.
    # The main end-to-end workflow is now refactored into agent.core.
    if args.llm_dump:
        if args.two_stage:
            l1_request = build_plan_request(
                args.question,
                repo_root / args.mapping,
                repo_root / args.plan_l1_schema,
                selected_tables=None,
            )
            l2_request = build_plan_request(
                args.question,
                repo_root / args.mapping,
                repo_root / args.plan_schema,
                selected_tables=[],
            )
            plan_request = {"l1": l1_request, "l2_template": l2_request}
        else:
            plan_request = build_plan_request(args.question, repo_root / args.mapping, repo_root / args.plan_schema)
        coder_payload = {
            "note": "Provide a plan JSON to build the SQL prompt.",
            "template": {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an NLQ SQL planner. Build a read-only SELECT query. Use only listed tables and columns. Return JSON only.",
                    },
                    {
                        "role": "user",
                        "content": "Dataset: {table}\\nColumns: {columns}\\nJoin hints: {joins}\\nPlan JSON: {plan}\\nSchema: {sql_schema}",
                    },
                ]
            },
        }
        if args.plan_json:
            plan_path = Path(args.plan_json)
            plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
            coder_payload = build_sql_request(plan_payload, repo_root / args.mapping, repo_root / args.sql_schema)
        dump_payload = {
            "planner": plan_request,
            "coder": coder_payload,
        }
        Path(args.llm_dump).write_text(json.dumps(dump_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"Wrote LLM request payloads to {args.llm_dump}")
        return

    if args.planner_response:
        plan_payload = json.loads(Path(args.planner_response).read_text(encoding="utf-8"))
        if isinstance(plan_payload, dict) and plan_payload.get("datasets") and not plan_payload.get("dataset"):
            selected = [str(item) for item in plan_payload.get("datasets", []) if item]
            question_value = args.question
            if question_value == "ignored":
                question_value = str(plan_payload.get("original_question", "")) or question_value
            l2_request = build_plan_request(
                question_value,
                repo_root / args.mapping,
                repo_root / args.plan_schema,
                selected_tables=selected,
            )
            out_path = args.planner_response_out
            if not out_path and args.auto_next:
                out_path = "planner_response_l2_prompt.json"
            if out_path:
                Path(out_path).write_text(
                    json.dumps(l2_request, ensure_ascii=True, indent=2),
                    encoding="utf-8",
                )
            print_json("planner_l2_messages", l2_request)
        else:
            coder_payload = build_sql_request(plan_payload, repo_root / args.mapping, repo_root / args.sql_schema)
            out_path = args.planner_response_out
            if not out_path and args.auto_next:
                out_path = "coder_messages.json"
            if out_path:
                Path(out_path).write_text(
                    json.dumps(coder_payload, ensure_ascii=True, indent=2),
                    encoding="utf-8",
                )
            print_json("coder_messages", coder_payload)
        return

    if args.coder_response or args.manual_run:
        if args.coder_response:
            sql_payload = json.loads(Path(args.coder_response).read_text(encoding="utf-8"))
        else:  # args.manual_run
            if not args.sql_json:
                raise SystemExit("--manual-run requires --sql-json.")
            sql_payload = json.loads(Path(args.sql_json).read_text(encoding="utf-8"))

        sql = sql_payload.get("sql")
        if not sql:
            raise SystemExit("Input JSON must contain a non-empty 'sql' field.")
        sql = str(sql).lstrip("\ufeff").strip().rstrip(";")
        validate_sql_tables(sql, repo_root / args.mapping)
        print_json("sql", sql)

        if args.dry_run:
            return

        # MCP execution logic is preserved for manual/debug flows
        if not args.direct:
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
                    rows = result.structuredContent if result.structuredContent is not None else result.content
        else:
            rows = execute_direct_sql(sql)

        rows = sanitize_rows(apply_pii_mask(rows))
        print_json("rows", rows)
        if args.interpret:
            insight = summarize_rows(rows)
            print_json("insight", insight)
        if args.dump_output:
            payload = {"sql": sql, "rows": rows, "insight": insight if args.interpret else None}
            Path(args.dump_output).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        if args.interpret_prompt_out:
            metric_semantics = load_metric_semantics(repo_root)
            allowed_metrics = sorted(metric_semantics.keys())
            prompt = {
                "messages": [
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
                                "question": args.question if args.question != "ignored" else "",
                                "sql": sql,
                                "rows": rows,
                                "insight": insight if args.interpret else None,
                                "metric_semantics": metric_semantics,
                                "allowed_metrics": allowed_metrics,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ]
            }
            Path(args.interpret_prompt_out).write_text(
                json.dumps(prompt, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return

    if args.dry_run:
        client = LLMClient()
        if args.two_stage:
            plan, plan_debug = await plan_question_two_stage(
                args.question,
                repo_root / args.mapping,
                repo_root / args.plan_l1_schema,
                repo_root / args.plan_schema,
                client,
                debug=args.debug,
            )
        else:
            plan, plan_debug = await plan_question(
                args.question,
                repo_root / args.mapping,
                repo_root / args.plan_schema,
                client,
                debug=args.debug,
            )

        sql_payload, sql_debug = await plan_to_sql(
            plan,
            repo_root / args.mapping,
            repo_root / args.sql_schema,
            client,
            debug=args.debug,
        )

        if args.debug:
            if args.two_stage:
                print_json("llm_request_planner_l1", plan_debug.get("l1_request", {}))
                print_json("llm_response_planner_l1", plan_debug.get("l1_response", {}))
                if plan_debug.get("l1_raw") is not None:
                    print_json("llm_raw_planner_l1", plan_debug["l1_raw"])
                print_json("llm_request_planner_l2", plan_debug.get("l2_request", {}))
                print_json("llm_response_planner_l2", plan_debug.get("l2_response", {}))
                if plan_debug.get("l2_raw") is not None:
                    print_json("llm_raw_planner_l2", plan_debug["l2_raw"])
            else:
                print_json("llm_request_planner", plan_debug.get("llm_request", {}))
                print_json("llm_response_planner", plan_debug.get("llm_response", {}))
                if "llm_raw" in plan_debug:
                    print_json("llm_raw_planner", plan_debug["llm_raw"])

            print_json("llm_request_coder", sql_debug.get("llm_request", {}))
            print_json("llm_response_coder", sql_debug.get("llm_response", {}))
            if "llm_raw" in sql_debug:
                print_json("llm_raw_coder", sql_debug["llm_raw"])

        print_json("plan", plan)
        print_json("sql_payload", sql_payload)
        return

    # Default end-to-end execution using the refactored core workflow
    try:
        result = await run_nlq_workflow(
            question=args.question,
            two_stage=args.two_stage,
            execute=not args.dry_run,
            interpret=args.interpret,
            direct=args.direct,
            repo_root=repo_root,
        )
        print_json("plan", result["plan"])
        print_json("sql_payload", {"sql": result["sql"]})
        print_json("rows", result["rows"])
        if result.get("insight"):
            print_json("insight", result["insight"])

        if args.dump_output:
            Path(args.dump_output).write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
    except Exception as e:
        print(f"An error occurred during the workflow: {e}", file=sys.stderr)
        # The exception is already logged inside run_nlq_workflow, so just exit
        raise SystemExit(1) from e


if __name__ == "__main__":
    anyio.run(run)
