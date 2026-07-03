import re
from typing import Dict, List

from semantic.semantic_layer import dataset_columns, dataset_summaries, find_dataset_by_keyword


def is_sex_age_column(column: str) -> bool:
    return bool(re.fullmatch(r"(m|w)_(\d{4}|70u)", column))


def select_datasets(question: str, mapping: Dict[str, object]) -> List[Dict[str, object]]:
    hits = find_dataset_by_keyword(mapping, question)
    ordered = hits[:]
    for ds in mapping.get("datasets", []):  # type: ignore[assignment]
        if ds not in ordered:
            ordered.append(ds)
    return ordered


def build_l1_context(mapping: Dict[str, object]) -> str:
    lines = ["Allowed datasets (L1 summary):"]
    summaries = dataset_summaries({"datasets": mapping.get("datasets", [])})
    for item in summaries:
        table = item.get("table", "")
        name = item.get("name", "")
        synonyms = ", ".join(item.get("synonyms", []))
        lines.append(f"- {table}: {name}")
        if synonyms:
            lines.append(f"  keywords: {synonyms}")
        for ds in mapping.get("datasets", []):  # type: ignore[assignment]
            if ds.get("table") != table:
                continue
            description = ds.get("description")
            if description:
                lines.append(f"  description: {description}")
            domain = ds.get("domain")
            if domain:
                lines.append(f"  domain: {domain}")
            tags = ds.get("tags", [])
            if tags:
                lines.append(f"  tags: {', '.join(tags)}")
            break
    lines.append("")
    lines.append("Return JSON only. Use dataset names exactly as listed.")
    return "\n".join(lines)


def build_l2_context(
    mapping: Dict[str, object],
    selected_tables: List[str],
    max_tables: int | None = None,
) -> str:
    tables = []
    for ds in mapping.get("datasets", []):  # type: ignore[assignment]
        if ds.get("table") in selected_tables:
            tables.append(ds)
    if not tables:
        tables = list(mapping.get("datasets", []))  # type: ignore[assignment]

    summaries = dataset_summaries({"datasets": tables})
    if max_tables is not None:
        summaries = summaries[:max_tables]

    lines = ["Allowed datasets (L2 detail):"]
    for item in summaries:
        table = item.get("table", "")
        name = item.get("name", "")
        synonyms = ", ".join(item.get("synonyms", []))
        lines.append(f"- {table}: {name}")
        if synonyms:
            lines.append(f"  keywords: {synonyms}")
        for ds in tables:  # type: ignore[assignment]
            if ds.get("table") != table:
                continue
            description = ds.get("description")
            if description:
                lines.append(f"  description: {description}")
            columns = dataset_columns(ds)
            if columns:
                lines.append(f"  columns: {', '.join(columns)}")
            breakdowns = []
            if "sex_age" in columns:
                breakdowns.append("sex_age")
            elif any(is_sex_age_column(col) for col in columns):
                breakdowns.append("sex_age_columns (m_*/w_* age buckets)")
            if "time" in columns:
                breakdowns.append("time")
            if "hcode" in columns:
                breakdowns.append("hcode")
            if "inflow_cd" in columns:
                breakdowns.append("inflow_cd")
            if breakdowns:
                lines.append(f"  breakdowns: {', '.join(breakdowns)}")
            joins = ds.get("joins", [])
            for join in joins:
                column = join.get("column")
                ref_table = join.get("ref_table")
                ref_column = join.get("ref_column")
                ref_name = join.get("ref_name")
                description = join.get("description")
                if column and ref_table and ref_column:
                    detail = f"{column} -> {ref_table}.{ref_column}"
                    if ref_name:
                        detail += f" (name: {ref_table}.{ref_name})"
                    if description:
                        detail += f" (hint: {description})"
                    lines.append(f"  join: {detail}")
            constraints = ds.get("constraints", [])
            if constraints:
                lines.append(f"  constraints: {', '.join(constraints)}")
            samples = ds.get("samples", {})
            if isinstance(samples, dict) and samples:
                sample_items = []
                for key, value in list(samples.items())[:6]:
                    sample_items.append(f"{key}={value}")
                lines.append(f"  samples: {', '.join(sample_items)}")
            break

    lines.append("")
    lines.append("Return JSON only. Use dataset names exactly as listed.")
    return "\n".join(lines)


def build_dynamic_context(question: str, mapping: Dict[str, object], max_tables: int | None = None) -> str:
    tables = select_datasets(question, mapping)
    return build_l2_context(mapping, [ds.get("table", "") for ds in tables], max_tables=max_tables)
