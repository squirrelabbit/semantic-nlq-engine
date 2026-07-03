import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg


def db_connect() -> psycopg.Connection:
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        raise SystemExit("POSTGRES_DB/USER/PASSWORD must be set in the environment.")
    dsn = f"dbname={db} user={user} password={password} host={host} port={port}"
    return psycopg.connect(dsn)


def fetch_latest_dates(conn: psycopg.Connection) -> Tuple[str, Optional[str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(std_ymd) FROM sungnam_service_inflow_pop")
        current = cur.fetchone()[0]
        if not current:
            raise SystemExit("No data in sungnam_service_inflow_pop.")
        cur.execute(
            "SELECT MAX(std_ymd) FROM sungnam_service_inflow_pop WHERE std_ymd < %s",
            (current,),
        )
        previous = cur.fetchone()[0]
    return str(current), str(previous) if previous else None


def fetch_total_pop(conn: psycopg.Connection, std_ymd: str) -> float:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(h_pop + w_pop + v_pop), 0)
            FROM sungnam_service_inflow_pop
            WHERE std_ymd = %s
            """,
            (std_ymd,),
        )
        return float(cur.fetchone()[0])


def fetch_top_changes(
    conn: psycopg.Connection, current: str, previous: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH current AS (
              SELECT hcode, SUM(h_pop + w_pop + v_pop) AS pop
              FROM sungnam_service_inflow_pop
              WHERE std_ymd = %s
              GROUP BY hcode
            ),
            prev AS (
              SELECT hcode, SUM(h_pop + w_pop + v_pop) AS pop
              FROM sungnam_service_inflow_pop
              WHERE std_ymd = %s
              GROUP BY hcode
            ),
            joined AS (
              SELECT
                c.hcode,
                c.pop AS current_pop,
                p.pop AS prev_pop,
                (c.pop - COALESCE(p.pop, 0)) AS diff,
                CASE
                  WHEN p.pop IS NULL OR p.pop = 0 THEN NULL
                  ELSE (c.pop - p.pop) / p.pop
                END AS diff_rate
              FROM current c
              LEFT JOIN prev p ON c.hcode = p.hcode
            )
            SELECT
              pc.name,
              current_pop,
              prev_pop,
              diff,
              diff_rate
            FROM joined j
            JOIN place_codes pc ON j.hcode = pc.admin_code
            WHERE
              (pc.created_at IS NULL OR pc.created_at <= %s)
              AND (pc.abolished_at IS NULL OR pc.abolished_at >= %s)
            ORDER BY diff_rate DESC NULLS LAST
            LIMIT 3
            """,
            (current, previous, current, current),
        )
        increase = [
            {
                "region": row[0],
                "change_rate": float(row[4]) if row[4] is not None else None,
                "diff": float(row[3]),
            }
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            WITH current AS (
              SELECT hcode, SUM(h_pop + w_pop + v_pop) AS pop
              FROM sungnam_service_inflow_pop
              WHERE std_ymd = %s
              GROUP BY hcode
            ),
            prev AS (
              SELECT hcode, SUM(h_pop + w_pop + v_pop) AS pop
              FROM sungnam_service_inflow_pop
              WHERE std_ymd = %s
              GROUP BY hcode
            ),
            joined AS (
              SELECT
                c.hcode,
                c.pop AS current_pop,
                p.pop AS prev_pop,
                (c.pop - COALESCE(p.pop, 0)) AS diff,
                CASE
                  WHEN p.pop IS NULL OR p.pop = 0 THEN NULL
                  ELSE (c.pop - p.pop) / p.pop
                END AS diff_rate
              FROM current c
              LEFT JOIN prev p ON c.hcode = p.hcode
            )
            SELECT
              pc.name,
              current_pop,
              prev_pop,
              diff,
              diff_rate
            FROM joined j
            JOIN place_codes pc ON j.hcode = pc.admin_code
            WHERE
              (pc.created_at IS NULL OR pc.created_at <= %s)
              AND (pc.abolished_at IS NULL OR pc.abolished_at >= %s)
            ORDER BY diff_rate ASC NULLS LAST
            LIMIT 3
            """,
            (current, previous, current, current),
        )
        decrease = [
            {
                "region": row[0],
                "change_rate": float(row[4]) if row[4] is not None else None,
                "diff": float(row[3]),
            }
            for row in cur.fetchall()
        ]
    return increase, decrease


def detect_anomalies(
    increase: List[Dict[str, Any]],
    decrease: List[Dict[str, Any]],
    threshold: float = 0.2,
) -> List[Dict[str, Any]]:
    anomalies = []
    for item in increase + decrease:
        rate = item.get("change_rate")
        if rate is not None and abs(rate) >= threshold:
            anomalies.append(item)
    return anomalies


def apply_pii_mask(value: Any, threshold: float = 5.0) -> Any:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    return "MASKED" if num < threshold else value


def sanitize_value(value: Any) -> Any:
    if value is None:
        return "-"
    return value


def build_summary(current_total: float, previous_total: float) -> str:
    diff = current_total - previous_total
    rate = diff / previous_total if previous_total else 0.0
    direction = "증가" if diff >= 0 else "감소"
    return (
        f"전일 대비 전체 유입 인구가 {direction}했습니다. "
        f"변화량은 {diff:,.0f}명, 변화율은 {rate:.1%}입니다."
    )


def main() -> None:
    with db_connect() as conn:
        current, previous = fetch_latest_dates(conn)
        if not previous:
            raise SystemExit("이전 일자 데이터가 없습니다.")

        current_total = fetch_total_pop(conn, current)
        previous_total = fetch_total_pop(conn, previous)
        increase, decrease = fetch_top_changes(conn, current, previous)

    anomalies = detect_anomalies(increase, decrease)
    summary = build_summary(current_total, previous_total)
    summary_lines = [summary, "가장 큰 변화 지역을 중심으로 추가 분석이 필요합니다."]

    report = {
        "title": "일일 인구 자동 분석 리포트",
        "date": current,
        "summary": " ".join(summary_lines),
        "top_changes": {
            "increase": [
                {
                    "region": item["region"],
                    "change_rate": sanitize_value(apply_pii_mask(item["change_rate"])),
                    "diff": sanitize_value(apply_pii_mask(item["diff"])),
                }
                for item in increase
            ],
            "decrease": [
                {
                    "region": item["region"],
                    "change_rate": sanitize_value(apply_pii_mask(item["change_rate"])),
                    "diff": sanitize_value(apply_pii_mask(item["diff"])),
                }
                for item in decrease
            ],
        },
        "anomalies": (
            {
                "status": "alert",
                "message": "기준 초과 지역이 있습니다.",
                "items": anomalies,
            }
            if anomalies
            else {
                "status": "none",
                "message": "통계적 이상 징후 없음",
                "items": [],
            }
        ),
        "context": {
            "events": [],
            "note": "관련 맥락 데이터 없음",
        },
        "data_status": {
            "std_ymd": current,
            "admin_code_correction": True,
            "pii_masking": True,
        },
    }

    output_dir = Path("reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"daily_report_{current}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
