import json
import re
from pathlib import Path


CONTEXT = {
    "pop": "http://example.org/ontology/population#",
    "schema": "http://schema.org/",
    "Relation": "schema:Relation",
    "Dataset": "schema:Dataset",
    "Dimension": "pop:Dimension",
    "Measure": "pop:Measure",
    "name": "schema:name",
    "description": "schema:description",
    "table": "pop:table",
    "column": "pop:column",
    "semanticTag": "pop:semanticTag",
    "role": "pop:role",
    "source": {"@id": "pop:source", "@type": "@id"},
    "target": {"@id": "pop:target", "@type": "@id"},
}


DIMENSIONS = {
    "time": {"id": "pop:dimension:time", "name": "Time Dimension"},
    "location": {"id": "pop:dimension:location", "name": "Location Dimension"},
    "sex_age": {"id": "pop:dimension:sex_age", "name": "SexAge Dimension"},
}


AGE_MEASURE_RE = re.compile(r"^[mw]_\\d{2}(\\d{2}|u)$", re.IGNORECASE)
TIME_BUCKET_RE = re.compile(r"^time_\\d{2}$", re.IGNORECASE)


def infer_tags(column: str) -> set[str]:
    col = column.lower()
    tags = set()

    if col in ("std_ym", "std_ymd", "time"):
        tags.add("time")

    if col in ("hcode", "sgng_cd", "inflow_cd", "x_coord", "y_coord"):
        tags.add("location")

    if col == "sex_age":
        tags.add("dimension")

    if TIME_BUCKET_RE.match(col):
        tags.add("measure")

    if AGE_MEASURE_RE.match(col):
        tags.add("measure")

    return tags


def load_metadata(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run scripts/generate_metadata_jsonld.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def build_graph(metadata: dict) -> list[dict]:
    graph = []

    # Dimension nodes
    for dim in DIMENSIONS.values():
        graph.append(
            {
                "@id": dim["id"],
                "@type": "Dimension",
                "name": dim["name"],
            }
        )

    properties = [node for node in metadata.get("@graph", []) if node.get("@type") == "Property"]
    datasets = [node for node in metadata.get("@graph", []) if node.get("@type") == "Dataset"]

    # Create dataset nodes (as lightweight references)
    for dataset in datasets:
        graph.append(
            {
                "@id": f"pop:{dataset['table']}",
                "@type": "Dataset",
                "name": dataset.get("name"),
                "table": dataset.get("table"),
            }
        )

    # Link dataset -> dimension/measure via relations
    for prop in properties:
        tags = set(prop.get("tags", []))
        tags |= infer_tags(prop.get("column", ""))
        table = prop.get("table")
        if not table:
            continue

        dataset_id = f"pop:{table}"
        prop_id = f"pop:{table}:{prop.get('column')}"

        # Tag-specific relations
        if "time" in tags:
            graph.append(
                {
                    "@id": f"pop:rel:{table}:{prop.get('column')}:time",
                    "@type": "Relation",
                    "role": "uses_dimension",
                    "source": dataset_id,
                    "target": DIMENSIONS["time"]["id"],
                }
            )
        if "location" in tags:
            graph.append(
                {
                    "@id": f"pop:rel:{table}:{prop.get('column')}:location",
                    "@type": "Relation",
                    "role": "uses_dimension",
                    "source": dataset_id,
                    "target": DIMENSIONS["location"]["id"],
                }
            )
        if prop.get("column") == "sex_age" or "dimension" in tags:
            graph.append(
                {
                    "@id": f"pop:rel:{table}:{prop.get('column')}:sex_age",
                    "@type": "Relation",
                    "role": "uses_dimension",
                    "source": dataset_id,
                    "target": DIMENSIONS["sex_age"]["id"],
                }
            )

        if "measure" in tags:
            graph.append(
                {
                    "@id": prop_id,
                    "@type": "Measure",
                    "name": prop.get("column"),
                    "table": table,
                    "column": prop.get("column"),
                    "description": prop.get("description"),
                }
            )
            graph.append(
                {
                    "@id": f"pop:rel:{table}:{prop.get('column')}:measure",
                    "@type": "Relation",
                    "role": "has_measure",
                    "source": dataset_id,
                    "target": prop_id,
                }
            )

    return graph


def main() -> None:
    metadata_path = Path("ontology/metadata.jsonld")
    metadata = load_metadata(metadata_path)

    output = {
        "@context": CONTEXT,
        "@graph": build_graph(metadata),
    }
    out_path = Path("ontology/relation_graph.jsonld")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
