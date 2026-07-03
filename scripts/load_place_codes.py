import argparse
import os
from pathlib import Path
from typing import Iterable, Iterator

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


def detect_encoding(path: Path) -> str:
    for enc in ("cp949", "euc-kr", "utf-8"):
        try:
            path.read_text(encoding=enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "cp949"


def rows_from_file(path: Path, encoding: str, errors: str = "replace") -> Iterator[tuple]:
    with path.open("r", encoding=encoding, errors=errors) as f:
        header = f.readline()
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            code, name, status = parts[0], parts[1], parts[2]
            sgng_cd = code[:5] if len(code) >= 5 else ""
            is_sgng = code.endswith("00000")
            yield (
                code,
                name,
                status,
                sgng_cd,
                is_sgng,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            )


def rows_from_xlsx(path: Path) -> Iterable[tuple]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("pandas is required to read .xlsx files.") from exc

    df = pd.read_excel(path, sheet_name=0, dtype=str)
    df = df.fillna("")
    for _, row in df.iterrows():
        code = row.get("법정동코드", "")
        if not code:
            continue
        code = str(code)
        admin_code = str(row.get("행정동코드", "") or "")
        sido = str(row.get("시도명", "") or "")
        sigungu = str(row.get("시군구명", "") or "")
        eupmyeondong = str(row.get("읍면동명", "") or "")
        dongri = str(row.get("동리명", "") or "")
        created_at = str(row.get("생성일자", "") or "")
        abolished_at = str(row.get("말소일자", "") or "")
        parts = [sido, sigungu, eupmyeondong, dongri]
        name = " ".join([part for part in parts if part]).strip()
        status = "말소" if abolished_at else "존재"
        sgng_cd = code[:5] if len(code) >= 5 else ""
        is_sgng = code.endswith("00000")
        yield (
            code,
            name,
            status,
            sgng_cd,
            is_sgng,
            admin_code,
            sido,
            sigungu,
            eupmyeondong,
            dongri,
            created_at,
            abolished_at,
        )


def ensure_columns(cur: psycopg.Cursor) -> None:
    cur.execute(
        """
        ALTER TABLE place_codes
          ADD COLUMN IF NOT EXISTS admin_code text,
          ADD COLUMN IF NOT EXISTS sido_name text,
          ADD COLUMN IF NOT EXISTS sigungu_name text,
          ADD COLUMN IF NOT EXISTS eupmyeondong_name text,
          ADD COLUMN IF NOT EXISTS dongri_name text,
          ADD COLUMN IF NOT EXISTS created_at text,
          ADD COLUMN IF NOT EXISTS abolished_at text;
        """
    )


def write_utf8_copy(source: Path, dest: Path, encoding: str) -> int:
    count = 0
    with source.open("r", encoding=encoding, errors="replace") as src:
        with dest.open("w", encoding="utf-8") as out:
            for line in src:
                out.write(line)
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Reload place_codes from 법정동코드 file.")
    parser.add_argument(
        "--input",
        default="data/법정동코드 전체자료.txt",
        help="Path to 법정동코드 전체자료.txt or KIKmix.xlsx",
    )
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE place_codes before load.")
    parser.add_argument(
        "--utf8-output",
        default="data/법정동코드_전체자료_utf8.txt",
        help="Path to write UTF-8 converted copy.",
    )
    parser.add_argument("--convert-only", action="store_true", help="Only write UTF-8 copy and exit.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    input_path = repo_root / args.input
    if not input_path.exists():
        raise SystemExit(f"Missing input file: {input_path}")

    rows: list[tuple]
    if input_path.suffix.lower() == ".xlsx":
        raw_rows = list(rows_from_xlsx(input_path))
        deduped = {}
        for row in raw_rows:
            code = row[0]
            if code in deduped:
                continue
            deduped[code] = row
        rows = list(deduped.values())
        if args.convert_only:
            raise SystemExit("--convert-only is only supported for text input.")
    else:
        encoding = detect_encoding(input_path)
        utf8_path = repo_root / args.utf8_output
        lines = write_utf8_copy(input_path, utf8_path, encoding)
        print(f"Wrote UTF-8 copy to {utf8_path} (lines={lines}, source_encoding={encoding}).")
        if args.convert_only:
            return
        rows = list(rows_from_file(utf8_path, "utf-8", errors="strict"))

    with psycopg.connect(build_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("SET client_encoding TO 'UTF8'")
            ensure_columns(cur)
            if args.truncate:
                cur.execute("TRUNCATE TABLE place_codes;")
            with cur.copy(
                "COPY place_codes (code, name, status, sgng_cd, is_sgng, admin_code, sido_name, sigungu_name, eupmyeondong_name, dongri_name, created_at, abolished_at) FROM STDIN WITH (FORMAT CSV, DELIMITER '\t')"
            ) as copy:
                for row in rows:
                    copy.write_row(row)
        conn.commit()

    source_label = input_path if input_path.suffix.lower() == ".xlsx" else utf8_path
    print(f"Loaded {len(rows)} rows from {source_label}.")


if __name__ == "__main__":
    main()
