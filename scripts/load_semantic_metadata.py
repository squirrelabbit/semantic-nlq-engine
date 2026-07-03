import json
import os
from pathlib import Path

import psycopg


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


def load_mapping(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    mapping_path = repo_root / "semantic/semantic_mapping.json"
    mapping = load_mapping(mapping_path)
    datasets = mapping.get("datasets", [])

    with psycopg.connect(build_dsn()) as conn:
        with conn.cursor() as cur:
            for ds in datasets:
                cur.execute(
                    """
                    INSERT INTO semantic_metadata (
                      target_table,
                      business_name,
                      semantic_desc,
                      join_rules,
                      allowed_metrics,
                      constraints,
                      samples,
                      updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (target_table) DO UPDATE
                    SET business_name = EXCLUDED.business_name,
                        semantic_desc = EXCLUDED.semantic_desc,
                        join_rules = EXCLUDED.join_rules,
                        allowed_metrics = EXCLUDED.allowed_metrics,
                        constraints = EXCLUDED.constraints,
                        samples = EXCLUDED.samples,
                        updated_at = NOW();
                    """,
                    (
                        ds.get("table"),
                        ds.get("name"),
                        ds.get("description"),
                        json.dumps(ds.get("joins", []), ensure_ascii=False),
                        ds.get("measures", []),
                        ds.get("constraints", []),
                        json.dumps(ds.get("samples", {}), ensure_ascii=False),
                    ),
                )
        conn.commit()

    print(f"Loaded {len(datasets)} semantic metadata rows.")


if __name__ == "__main__":
    main()
