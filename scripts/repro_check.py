import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import anyio

from agent.core import run_nlq_workflow


def canonicalize(payload: Dict[str, Any]) -> str:
    """
    Creates a canonical, reproducible signature of a query result's rows.
    It normalizes column aliases in the results before comparison.
    """
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return json.dumps(rows, ensure_ascii=False, sort_keys=True)

    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict):
            normalized_rows.append(row)
            continue
        
        new_row = {}
        for key, value in row.items():
            # Normalize keys by removing "total_" prefix
            new_key = key.replace("total_", "")
            new_row[new_key] = value
        normalized_rows.append(new_row)

    # Now, sort the list of normalized dictionaries
    try:
        stringified_rows = [json.dumps(d, ensure_ascii=False, sort_keys=True) for d in normalized_rows]
        stringified_rows.sort()
        return json.dumps(stringified_rows)
    except TypeError:
        return str(normalized_rows)


async def run_checks(question: str, runs: int, direct: bool, repo_root: Path) -> None:
    outputs: List[Dict[str, Any]] = []
    for _ in range(runs):
        result = await run_nlq_workflow(
            question=question,
            two_stage=True,
            execute=True,
            interpret=False,
            direct=direct,
            repo_root=repo_root,
        )
        outputs.append(
            {
                "sql": result.get("sql"),
                "rows": result.get("rows"),
            }
        )

    signatures = [canonicalize(output) for output in outputs]
    all_same = all(sig == signatures[0] for sig in signatures[1:])

    print("reproducibility:", "PASS" if all_same else "FAIL")
    for idx, output in enumerate(outputs, start=1):
        print(f"run_{idx}_sql:", output.get("sql"))
        print(f"run_{idx}_rows_count:", len(output.get("rows") or []))



def main() -> int:
    parser = argparse.ArgumentParser(description="Check reproducibility for an NLQ question.")
    parser.add_argument("question", help="Question to run repeatedly.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--direct", action="store_true", help="Use direct DB execution.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    anyio.run(run_checks, args.question, args.runs, args.direct, repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())