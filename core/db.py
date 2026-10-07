"""응시 세션·응답 저장 계층.

SQLAlchemy Core만 사용하므로 로컬 SQLite와 Supabase(Postgres)에서 같은 코드가 동작한다.
모든 함수는 Engine을 받아 Streamlit 없이도 테스트할 수 있다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.engine import Engine

metadata = sa.MetaData()

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("client_id", sa.String(36), nullable=False, index=True),  # 익명 브라우저 ID
    sa.Column("mode", sa.String(8), nullable=False),  # quick | full (규준은 모드별로 따로)
    sa.Column("series_id", sa.String(36), index=True),  # 같은 사람이 이어서 푼 라운드 묶음 (1라운드 세션 ID)
    sa.Column("round", sa.Integer, nullable=False, server_default="1"),
    sa.Column("is_first_attempt", sa.Boolean, nullable=False),
    sa.Column("form_seed", sa.Integer, nullable=False),
    sa.Column("app_version", sa.String(20), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
    sa.Column("raw_scores", sa.JSON),    # {"gf": 7, ...}
    sa.Column("domain_index", sa.JSON),  # {"gf": 108.2, ...} 가정 규준 기준 영역 지수
    sa.Column("thetas", sa.JSON),        # {"total": 0.53, "gf": 0.41, ...} 능력 추정치 (실제 규준 계산용)
    sa.Column("focus_lost", sa.Integer), # 검사 중 탭·창 이탈 횟수
    sa.Column("ltr_index", sa.Float),
    sa.Column("percentile", sa.Float),
    sa.Column("progress", sa.JSON),      # 응시 진행 상태 (새로고침 후 이어 풀기용)
)

responses = sa.Table(
    "responses",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False, index=True),
    sa.Column("item_id", sa.String(40), nullable=False, index=True),
    sa.Column("item_version", sa.Integer, nullable=False),
    sa.Column("domain", sa.String(8), nullable=False),
    sa.Column("answer", sa.Text),       # 미응답이면 NULL
    sa.Column("correct", sa.Boolean, nullable=False),
    sa.Column("score", sa.Float, nullable=False),  # 0/1, 처리속도 블록은 맞힌 개수
    sa.Column("response_ms", sa.Integer),
    sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)


def start_session(engine: Engine, client_id: str, mode: str, form_seed: int, app_version: str,
                  series_id: str | None = None, round_no: int = 1) -> str:
    session_id = str(uuid.uuid4())
    with engine.begin() as conn:
        # 같은 브라우저에서 완료한 세션이 이미 있으면 규준 계산에서 제외할 재응시로 표시
        prior = conn.execute(
            sa.select(sa.func.count())
            .select_from(sessions)
            .where(sessions.c.client_id == client_id, sessions.c.completed_at.is_not(None))
        ).scalar_one()
        conn.execute(
            sessions.insert().values(
                id=session_id,
                client_id=client_id,
                mode=mode,
                series_id=series_id or session_id,
                round=round_no,
                is_first_attempt=prior == 0,
                form_seed=form_seed,
                app_version=app_version,
                started_at=_now(),
            )
        )
    return session_id


def save_responses(engine: Engine, session_id: str, rows: list[dict]) -> None:
    """rows: item_id, item_version, domain, answer, correct, score, response_ms."""
    if not rows:
        return
    now = _now()
    with engine.begin() as conn:
        # 저장 도중 끊겨 같은 영역을 다시 저장해도 응답이 두 번 쌓이지 않게 한다
        conn.execute(responses.delete().where(
            responses.c.session_id == session_id, responses.c.item_id.in_([r["item_id"] for r in rows])))
        conn.execute(
            responses.insert(),
            [{**r, "session_id": session_id, "answered_at": r.get("answered_at", now)} for r in rows],
        )


def complete_session(
    engine: Engine,
    session_id: str,
    raw_scores: dict,
    domain_index: dict,
    ltr_index: float,
    percentile: float,
    thetas: dict | None = None,
    focus_lost: int = 0,
) -> None:
    """결과를 기록하고 완료 처리한다. 이미 완료된 세션은 건드리지 않는다 (결과 화면 새로고침 대비)."""
    with engine.begin() as conn:
        conn.execute(
            sessions.update()
            .where(sessions.c.id == session_id, sessions.c.completed_at.is_(None))
            .values(
                completed_at=_now(),
                raw_scores=raw_scores,
                domain_index=domain_index,
                ltr_index=ltr_index,
                percentile=percentile,
                thetas=thetas,
                focus_lost=focus_lost,
            )
        )


def save_progress(engine: Engine, session_id: str, progress: dict) -> None:
    with engine.begin() as conn:
        conn.execute(sessions.update().where(sessions.c.id == session_id).values(progress=progress))


def load_session(engine: Engine, session_id: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(sa.select(sessions).where(sessions.c.id == session_id)).first()
    return dict(row._mapping) if row else None


def norm_raw_scores(engine: Engine, mode: str) -> list[dict]:
    """규준 계산용: 해당 모드에서 완료된 첫 응시 세션들의 영역별 원점수."""
    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(sessions.c.raw_scores).where(
                sessions.c.mode == mode,
                sessions.c.completed_at.is_not(None),
                sessions.c.is_first_attempt.is_(True),
            )
        ).all()
    return [r.raw_scores for r in rows]


def series_sessions(engine: Engine, series_id: str) -> list[dict]:
    """같은 라운드 묶음의 세션들 (라운드 순)."""
    with engine.connect() as conn:
        rows = conn.execute(sa.select(sessions).where(sessions.c.series_id == series_id)
                            .order_by(sessions.c.round)).all()
    return [dict(r._mapping) for r in rows]


def seen_items(engine: Engine, series_id: str) -> set[str]:
    """라운드 묶음에서 이미 출제된 문항 ID (추가 라운드가 겹치지 않게)."""
    q = sa.select(responses.c.item_id).join(sessions, sessions.c.id == responses.c.session_id)         .where(sessions.c.series_id == series_id)
    with engine.connect() as conn:
        return {r.item_id for r in conn.execute(q)}


def norm_thetas(engine: Engine, mode: str, exclude: str | None = None) -> list[dict]:
    """실제 규준 계산용: 해당 모드에서 완료된 첫 응시(1라운드) 세션들의 능력 추정치."""
    q = sa.select(sessions.c.thetas).where(
        sessions.c.mode == mode,
        sessions.c.round == 1,
        sessions.c.completed_at.is_not(None),
        sessions.c.is_first_attempt.is_(True),
        sessions.c.thetas.is_not(None),
    )
    if exclude:
        q = q.where(sessions.c.id != exclude)
    with engine.connect() as conn:
        return [r.thetas for r in conn.execute(q)]


def response_matrix(engine: Engine, first_attempt_only: bool = True) -> list[dict]:
    """문항 분석용: (session_id, item_id, domain, correct, score, response_ms) 전체."""
    q = sa.select(
        responses.c.session_id,
        responses.c.item_id,
        responses.c.item_version,
        responses.c.domain,
        responses.c.correct,
        responses.c.score,
        responses.c.response_ms,
    ).join(sessions, sessions.c.id == responses.c.session_id).where(sessions.c.completed_at.is_not(None))
    if first_attempt_only:
        q = q.where(sessions.c.is_first_attempt.is_(True))
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(q)]
