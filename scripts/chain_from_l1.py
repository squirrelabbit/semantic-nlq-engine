import argparse
import json
from pathlib import Path

from agent.coder import build_sql_request
from agent.planner import build_plan_request


def print_json(label: str, payload: object) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=True, indent=2, default=str)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chain L1 response to L2 prompt (and optional L2 response).")
    parser.add_argument("--l1-response", required=True, help="Planner L1 response JSON.")
    parser.add_argument("--l2-response", help="Planner L2 response JSON (optional).")
    parser.add_argument("--mapping", default="semantic/semantic_mapping.json")
    parser.add_argument("--plan-schema", default="agent/plan_schema.json")
    parser.add_argument("--sql-schema", default="agent/sql_schema.json")
    parser.add_argument("--l2-prompt-out", default="planner_response_l2_prompt.json")
    parser.add_argument("--l2-response-out", default="planner_response_l2.json")
    parser.add_argument("--coder-messages-out", default="coder_messages.json")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    l1_payload = json.loads(Path(args.l1_response).read_text(encoding="utf-8"))
    if not isinstance(l1_payload, dict) or not l1_payload.get("datasets"):
        raise SystemExit("l1-response must contain datasets.")

    selected = [str(item) for item in l1_payload.get("datasets", []) if item]
    question = l1_payload.get("original_question", "")
    l2_prompt = build_plan_request(
        question,
        repo_root / args.mapping,
        repo_root / args.plan_schema,
        selected_tables=selected,
    )
    Path(args.l2_prompt_out).write_text(
        json.dumps(l2_prompt, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print_json("planner_l2_messages", l2_prompt)

    if not args.l2_response:
        return

    l2_payload = json.loads(Path(args.l2_response).read_text(encoding="utf-8"))
    if not isinstance(l2_payload, dict) or not l2_payload.get("dataset"):
        raise SystemExit("l2-response must contain dataset.")

    Path(args.l2_response_out).write_text(
        json.dumps(l2_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    coder_payload = build_sql_request(l2_payload, repo_root / args.mapping, repo_root / args.sql_schema)
    Path(args.coder_messages_out).write_text(
        json.dumps(coder_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print_json("coder_messages", coder_payload)


if __name__ == "__main__":
    main()
