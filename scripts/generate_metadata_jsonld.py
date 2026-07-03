import json
import os
import re
from pathlib import Path

import psycopg


CONTEXT = {
    "pop": "http://example.org/ontology/population#",
    "schema": "http://schema.org/",
    "Dataset": "schema:Dataset",
    "Property": "schema:Property",
    "name": "schema:name",
    "description": "schema:description",
    "table": "pop:table",
    "column": "pop:column",
    "semanticTag": "pop:semanticTag",
    "dataType": "pop:dataType",
    "tags": "pop:tags",
    "hasProperty": {"@id": "pop:hasProperty", "@type": "@id"},
}


TABLE_LABELS = {
    "sungnam_service_inflow_pop": "행정동별 유입지별 서비스인구",
    "sungnam_service_sex_age_pop": "행정동별 성연령별 서비스인구",
    "sungnam_service_pcell_sex_age_pop": "CELL단위 성연령별 서비스인구",
    "sungnam_service_pcell_pop": "CELL단위 시간대별 서비스인구",
    "sungnam_unique_pop": "시군구단위 유니크인구",
}

BASE_COLUMN_LABELS = {
    "std_ym": "기준년월",
    "std_ymd": "기준년월일",
    "time": "시간",
    "inflow_cd": "유입지역 코드",
    "hcode": "행정동 코드",
    "sgng_cd": "시군구 코드",
    "sex_age": "성연령",
    "x_coord": "X좌표",
    "y_coord": "Y좌표",
    "h_pop": "주거인구(야간체류지)",
    "w_pop": "직장인구(주간체류지)",
    "v_pop": "방문인구",
}


AGE_MEASURE_RE = re.compile(r"^[mw]_\d{2}(\d{2}|u)$", re.IGNORECASE)
TIME_BUCKET_RE = re.compile(r"^time_\d{2}$", re.IGNORECASE)


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


def build_dsn() -> str:
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        raise ValueError("POSTGRES_DB/USER/PASSWORD must be set in the environment.")
    return f"dbname={db} user={user} password={password} host={host} port={port}"


def normalize_type(row: dict) -> str:
    data_type = row["data_type"].upper()
    char_len = row["character_maximum_length"]
    num_precision = row["numeric_precision"]
    num_scale = row["numeric_scale"]

    if data_type in ("CHARACTER VARYING", "VARCHAR"):
        if char_len:
            return f"VARCHAR({char_len})"
        return "VARCHAR"
    if data_type in ("CHARACTER", "CHAR"):
        if char_len:
            return f"CHAR({char_len})"
        return "CHAR"
    if data_type in ("NUMERIC", "DECIMAL"):
        if num_precision is not None and num_scale is not None:
            return f"NUMERIC({num_precision},{num_scale})"
        if num_precision is not None:
            return f"NUMERIC({num_precision})"
        return "NUMERIC"
    return data_type


def describe_column(column: str) -> str:
    col = column.lower()
    if col in BASE_COLUMN_LABELS:
        return BASE_COLUMN_LABELS[col]

    if TIME_BUCKET_RE.match(col):
        hour = col.split("_", 1)[1]
        return f"{hour}시 인구"

    if AGE_MEASURE_RE.match(col):
        sex = "남자" if col.startswith("m_") else "여자"
        bucket = col.split("_", 1)[1]
        if bucket.endswith("u"):
            return f"{sex}70세이상"
        return f"{sex}{bucket[:2]}세~{bucket[2:]}세"

    return column


def build_graph(schema_rows: list[dict]) -> list[dict]:
    graph = []
    tables = {}
    for row in schema_rows:
        tables.setdefault(row["table_name"], []).append(row)

    for table, columns in tables.items():
        if not table.startswith("sungnam_"):
            continue
        dataset_id = f"pop:{table}"
        prop_nodes = []
        for row in columns:
            col = row["column_name"]
            dtype = normalize_type(row)
            tags = set(infer_tags(col))
            if "measure" not in tags and "time" not in tags and "location" not in tags and "dimension" not in tags:
                if dtype.startswith("NUMERIC"):
                    tags.add("measure")
            prop_id = f"pop:{table}:{col}"
            prop_nodes.append(prop_id)
            graph.append(
                {
                    "@id": prop_id,
                    "@type": "Property",
                    "name": col,
                    "description": describe_column(col),
                    "table": table,
                    "column": col,
                    "dataType": dtype,
                    "tags": sorted(tags),
                }
            )
        graph.append(
            {
                "@id": dataset_id,
                "@type": "Dataset",
                "name": TABLE_LABELS.get(table, table),
                "table": table,
                "hasProperty": prop_nodes,
            }
        )
    return graph


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")
    with psycopg.connect(build_dsn()) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT table_name, column_name, data_type,
                       character_maximum_length, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position;
                """
            )
            rows = cur.fetchall()

    output = {"@context": CONTEXT, "@graph": build_graph(rows)}
    out_path = Path("ontology/metadata.jsonld")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
