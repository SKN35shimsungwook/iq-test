"""Streamlit 런타임 공용 리소스: DB 엔진, 문항은행, 세션 상태 초기화."""

from __future__ import annotations

import uuid
from pathlib import Path

import streamlit as st
from sqlalchemy.engine import Engine

from core import db
from core.item_bank import load_items
from core.schema import Item

APP_VERSION = "0.1.0"
LOCAL_DB = Path(__file__).resolve().parent.parent / "data" / "iq_test.db"


def _has_sql_secret() -> bool:
    try:
        return "sql" in st.secrets.get("connections", {})
    except Exception:  # secrets.toml 자체가 없을 때
        return False


@st.cache_resource
def get_engine() -> Engine:
    """secrets에 [connections.sql]이 있으면 그것(Supabase), 없으면 로컬 SQLite."""
    if _has_sql_secret():
        conn = st.connection("sql", type="sql")
    else:
        LOCAL_DB.parent.mkdir(exist_ok=True)
        conn = st.connection("sql", type="sql", url=f"sqlite:///{LOCAL_DB.as_posix()}")
    db.init_db(conn.engine)
    return conn.engine


@st.cache_data
def get_items() -> list[Item]:
    return load_items()


def init_state() -> None:
    ss = st.session_state
    # TODO(3단계): 브라우저 localStorage 기반 ID로 교체해 새로고침 후에도 재응시를 판별
    ss.setdefault("client_id", str(uuid.uuid4()))
    ss.setdefault("session_id", None)  # 검사 시작 시 DB 세션 ID
    ss.setdefault("mode", None)        # Mode.QUICK | Mode.FULL
    ss.setdefault("form_seed", None)
    ss.setdefault("phase", "intro")    # intro → test → result
