import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_mapping(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing semantic mapping: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def dataset_summaries(mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"table": ds["table"], "name": ds.get("name", ""), "synonyms": ds.get("synonyms", [])}
        for ds in mapping.get("datasets", [])
    ]


def find_dataset_by_keyword(mapping: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    hits = []
    lowered = text.lower()
    for ds in mapping.get("datasets", []):
        for keyword in ds.get("synonyms", []):
            if keyword in lowered:
                hits.append(ds)
                break
    return hits


def resolve_metric_columns(mapping: Dict[str, Any], metric_name: str) -> List[str]:
    for metric in mapping.get("metrics", []):
        if metric.get("name") == metric_name:
            return metric.get("columns", [])
    return []


def get_dataset(mapping: Dict[str, Any], table: str) -> Optional[Dict[str, Any]]:
    for ds in mapping.get("datasets", []):
        if ds.get("table") == table:
            return ds
    return None


def dataset_columns(dataset: Dict[str, Any]) -> List[str]:
    columns: List[str] = []
    for group in dataset.get("dimensions", {}).values():
        columns.extend(group)
    columns.extend(dataset.get("measures", []))
    return columns
