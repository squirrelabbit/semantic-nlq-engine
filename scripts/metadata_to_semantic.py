import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_dimension_bucket(column: dict) -> str | None:
    name = column.get("name", "")
    tags = set(column.get("tags", []))
    if "#시간" in tags or name in ("std_ymd", "std_ym", "time") or name.startswith("time_"):
        return "time"
    if "#지역" in tags or name in ("hcode", "inflow_cd", "sgng_cd", "code", "name"):
        return "location"
    if "#성별" in tags or "#연령" in tags or name == "sex_age":
        return "sex_age"
    if "#좌표" in tags or name in ("x_coord", "y_coord"):
        return "location"
    return None


def is_measure(name: str, role: str) -> bool:
    if role == "measure":
        return True
    if name.startswith("time_"):
        return True
    if name.startswith(("m_", "w_")):
        return True
    if name.endswith("_pop") or name in ("h_pop", "w_pop", "v_pop"):
        return True
    return False


def short_name(table: str, description: str) -> str:
    if description and len(description) <= 20:
        return description
    return table


def build_dataset_entry(dataset: dict, existing: dict | None) -> dict:
    table = dataset.get("table", "")
    description = dataset.get("description", "")
    columns = dataset.get("columns", [])

    dimensions: dict[str, list[str]] = {}
    measures: list[str] = []
    samples: dict[str, object] = {}
    dataset_tags: set[str] = set()
    for col in columns:
        name = col.get("name", "")
        role = col.get("role", "")
        if not name:
            continue
        for tag in col.get("tags", []):
            dataset_tags.add(tag)
        sample_value = col.get("sample_value")
        if sample_value is not None:
            samples[name] = sample_value
        if is_measure(name, role):
            measures.append(name)
            continue
        bucket = infer_dimension_bucket(col)
        if bucket:
            dimensions.setdefault(bucket, []).append(name)

    synonyms = existing.get("synonyms", []) if existing else []
    joins = dataset.get("joins", []) if dataset.get("joins") else existing.get("joins", []) if existing else []
    tags = existing.get("tags", []) if existing else []
    if dataset_tags:
        tags = sorted(set(tags).union(dataset_tags))
    domain = existing.get("domain") if existing else None
    if not domain:
        if "#인구" in tags:
            domain = "population"
        elif "#지역" in tags or "#행정" in tags:
            domain = "geography"
        elif "#좌표" in tags:
            domain = "spatial"

    return {
        "table": table,
        "name": short_name(table, description),
        "description": description,
        "synonyms": synonyms,
        "domain": domain,
        "tags": tags,
        "dimensions": dimensions,
        "joins": joins,
        "measures": measures,
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert metadata_draft.json to semantic_mapping.json")
    parser.add_argument("--draft", default="ontology/metadata_draft.json")
    parser.add_argument("--mapping", default="semantic/semantic_mapping.json")
    parser.add_argument("--output", default="semantic/semantic_mapping.json")
    args = parser.parse_args()

    draft = load_json(Path(args.draft))
    existing_mapping = load_json(Path(args.mapping)) if Path(args.mapping).exists() else {"datasets": [], "metrics": []}
    existing_by_table = {ds.get("table"): ds for ds in existing_mapping.get("datasets", [])}

    datasets = []
    for ds in draft.get("datasets", []):
        table = ds.get("table")
        if not table:
            continue
        datasets.append(build_dataset_entry(ds, existing_by_table.get(table)))

    output = {
        "datasets": datasets,
        "metrics": existing_mapping.get("metrics", []),
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote semantic mapping to {output_path}")


if __name__ == "__main__":
    main()
