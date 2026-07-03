import argparse
import json
import os
from pathlib import Path

import requests


def build_summary(payload: dict) -> str:
    rows = payload.get("rows", {})
    result_rows = rows.get("result") if isinstance(rows, dict) else rows
    row_count = len(result_rows) if isinstance(result_rows, list) else 0
    sql = payload.get("sql", "")
    lines = [
        "*NLQ 결과 요약*",
        f"- rows: {row_count}",
        f"- sql: `{sql[:180]}{'...' if len(sql) > 180 else ''}`",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send NLQ result payload to Slack webhook.")
    parser.add_argument("--payload", default="result_payload.json")
    parser.add_argument("--webhook", default=os.getenv("SLACK_WEBHOOK_URL"))
    args = parser.parse_args()

    if not args.webhook:
        raise SystemExit("Missing Slack webhook. Set SLACK_WEBHOOK_URL or pass --webhook.")

    payload_path = Path(args.payload)
    if not payload_path.exists():
        raise SystemExit(f"Missing payload file: {payload_path}")

    data = json.loads(payload_path.read_text(encoding="utf-8"))
    text = build_summary(data)
    response = requests.post(args.webhook, json={"text": text}, timeout=10)
    if response.status_code >= 300:
        raise SystemExit(f"Slack error: {response.status_code} {response.text}")
    print("Sent Slack notification.")


if __name__ == "__main__":
    main()
