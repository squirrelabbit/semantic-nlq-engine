import os
from datetime import datetime, timedelta

import pandas as pd
import psycopg
import streamlit as st


def get_conn() -> psycopg.Connection:
    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    if not all([db, user, password]):
        raise RuntimeError("POSTGRES_DB/USER/PASSWORD must be set in the environment.")
    dsn = f"dbname={db} user={user} password={password} host={host} port={port}"
    return psycopg.connect(dsn)


def load_logs(conn: psycopg.Connection, days: int) -> pd.DataFrame:
    since = datetime.utcnow() - timedelta(days=days)
    query = """
        SELECT request_id, original_question, generated_sql, execution_time,
               error_message, status, created_at
        FROM execution_logs
        WHERE created_at >= %s
        ORDER BY created_at DESC
    """
    return pd.read_sql(query, conn, params=(since,))


st.set_page_config(page_title="Ontology Ops Dashboard", layout="wide")
st.title("Ontology Operational Dashboard")

days = st.sidebar.slider("최근 N일", min_value=1, max_value=30, value=7)

with st.spinner("로그 로딩 중..."):
    try:
        with get_conn() as conn:
            df = load_logs(conn, days)
    except Exception as exc:
        st.error(f"DB 연결 실패: {exc}")
        st.stop()

total = len(df)
success = int((df["status"] == "SUCCESS").sum()) if total else 0
fail = total - success
avg_time = df["execution_time"].mean() if total else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("총 실행", total)
col2.metric("성공", success)
col3.metric("실패", fail)
col4.metric("평균 응답 시간(초)", f"{avg_time:.3f}")

st.subheader("최근 실패 쿼리")
fail_df = df[df["status"] == "FAIL"].copy()
st.dataframe(fail_df.head(20), use_container_width=True)

st.subheader("최근 실행 로그")
st.dataframe(df.head(50), use_container_width=True)
