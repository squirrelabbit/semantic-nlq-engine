from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_metrics(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload.get("metrics", {}) if isinstance(payload, dict) else {}


def format_metric_context(metrics: Dict[str, Any]) -> str:
    if not metrics:
        return ""
    lines = ["Metric semantics (fixed meanings):"]
    for name, meta in metrics.items():
        display = meta.get("display_name", "")
        domain = meta.get("domain_meaning", "")
        description = meta.get("description", "")
        rules = meta.get("interpretation_rules", [])
        line = f"- {name}"
        if display:
            line += f": {display}"
        if domain:
            line += f" | {domain}"
        lines.append(line)
        if description:
            lines.append(f"  description: {description}")
        if rules:
            lines.append(f"  interpretation_rules: {', '.join(rules)}")
    return "\n".join(lines)
