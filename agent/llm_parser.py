import json
from typing import Any, Dict, Optional, Tuple


def extract_json(text: Optional[str]) -> Tuple[Dict[str, Any], Optional[str]]:
    if text is None:
        return {}, "Empty LLM response."

    stripped = text.strip()
    # Removed backtick stripping logic here
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}, "No JSON object found."
    snippet = stripped[start : end + 1]

    try:
        return json.loads(snippet), None
    except json.JSONDecodeError as exc:
        return {}, f"JSON parse error: {exc}"
