"""관리자 분석: 문항 분석, 신뢰도, 응시 흐름, 문항 모수 보정 (Streamlit 없이 테스트 가능한 순수 로직).

적응형 출제에서는 어려운 문항을 잘하는 사람만 보므로 단순 정답률이 실제 난이도를 왜곡한다.
그래서 문항마다 '그 문항을 본 사람들의 능력으로 모형이 예측한 정답률'과 실제 정답률을 비교한다.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from core import db
from core import exam as ex
from core import scoring as sc
from core.schema import BLUEPRINT, DEEP_ROUND, DIFFICULTY_LABELS, Domain, Item, ItemFormat, round_label

MIN_N = 30          # 문항 판정에 필요한 최소 응답 수
SIM_VERSION = "sim"  # 시뮬레이션 데이터 표시


def load_frames(engine: Engine, include_sim: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(세션, 응답) 데이터프레임. 응답에는 그 세션의 종합 θ가 붙는다."""
    with engine.connect() as conn:
        sessions = pd.DataFrame([dict(r._mapping) for r in conn.execute(sa.select(db.sessions))])
        responses = pd.DataFrame([dict(r._mapping) for r in conn.execute(sa.select(db.responses))])
    if sessions.empty:
        return sessions, responses
    if not include_sim:
        sessions = sessions[sessions["app_version"] != SIM_VERSION]
    sessions = sessions.assign(
        completed=sessions["completed_at"].notna(),
        theta=sessions["thetas"].map(lambda t: (t or {}).get("total") if isinstance(t, dict) else None),
    )
    if not responses.empty:
        responses = responses.merge(
            sessions[["id", "mode", "round", "is_first_attempt", "completed", "theta"]],
            left_on="session_id", right_on="id", suffixes=("", "_s"))
        responses = responses[responses["completed"]]
    return sessions, responses


def _p(item: Item, theta: np.ndarray) -> np.ndarray:
    a, b, c = sc.item_params(item)
    return c + (1 - c) / (1 + np.exp(-sc.D * a * (theta - b)))


def item_stats(responses: pd.DataFrame, items: dict[str, Item], min_n: int = MIN_N) -> pd.DataFrame:
    """문항별 통계와 경고. 처리속도(블록 점수)는 제외."""
    out = []
    df = responses[responses["theta"].notna()]
    for item_id, g in df.groupby("item_id"):
        it = items.get(item_id)
        if it is None or it.format is ItemFormat.SYMBOL_CODING:
            continue
        correct = g["correct"].astype(float).to_numpy()
        theta = g["theta"].astype(float).to_numpy()
        n = len(g)
        p_obs = correct.mean()
        p_each = _p(it, theta)
        p_pred = p_each.mean()
        z = (p_obs - p_pred) / (math.sqrt((p_each * (1 - p_each)).sum()) / n)  # 우연으로 생길 만한 차이인가
        r_pb = float(np.corrcoef(correct, theta)[0, 1]) if n > 2 and correct.std() > 0 and theta.std() > 0 else np.nan
        flags = []
        if n >= min_n:
            if p_obs > 0.9:
                flags.append("너무 쉬움")
            if p_obs < 0.1:
                flags.append("너무 어려움")
            if not np.isnan(r_pb) and r_pb < 0.2:
                flags.append("변별도 낮음")
            if p_obs - p_pred > 0.15 and z > 3:
                flags.append("예상보다 쉬움")
            if p_pred - p_obs > 0.15 and z < -3:
                flags.append("예상보다 어려움")
        out.append({
            "문항": item_id, "영역": BLUEPRINT[it.domain].label, "유형": it.subtype,
            "난이도": DIFFICULTY_LABELS[it.difficulty], "응답 수": n, "정답률": p_obs, "예측 정답률": p_pred,
            "차이": p_obs - p_pred, "변별도": r_pb,
            "응답 시간(초)": g["response_ms"].dropna().median() / 1000 if g["response_ms"].notna().any() else np.nan,
            "판정": ", ".join(flags) if flags else ("정상" if n >= min_n else "데이터 부족"),
        })
    return pd.DataFrame(out)


def domain_reliability(responses: pd.DataFrame, items: dict[str, Item]) -> pd.DataFrame:
    """영역별 주변 신뢰도 = var(θ̂) / (var(θ̂) + 평균 SE²). 적응형 검사에서 쓰는 신뢰도 지표."""
    rows = []
    totals, total_se = [], []
    for _, sg in responses.groupby("session_id"):
        _, tot = sc.estimate(sg[["item_id", "domain", "correct", "score"]].to_dict("records"), items)
        totals.append(tot.theta)
        total_se.append(tot.se)
    if len(totals) >= 3:
        var_t, mse = float(np.var(totals, ddof=1)), float(np.mean(np.square(total_se)))
        rows.append({"영역": "종합 (LTR Index)", "응시 수": len(totals), "신뢰도": var_t / (var_t + mse),
                     "평균 표준오차(지수)": 15 * float(np.mean(total_se))})
    for domain in sc.DOMAIN_ORDER:
        g = responses[responses["domain"] == domain.value]
        if g.empty:
            continue
        thetas, ses = [], []
        for _, sg in g.groupby("session_id"):
            recs = sg[["item_id", "domain", "correct", "score"]].to_dict("records")
            per, _ = sc.estimate(recs, items)
            if domain in per:
                thetas.append(per[domain].theta)
                ses.append(per[domain].se)
        if len(thetas) < 3:
            continue
        var_t, mse = float(np.var(thetas, ddof=1)), float(np.mean(np.square(ses)))
        rows.append({"영역": BLUEPRINT[domain].label, "응시 수": len(thetas),
                     "신뢰도": var_t / (var_t + mse) if var_t + mse > 0 else np.nan,
                     "평균 표준오차(지수)": 15 * float(np.mean(ses))})
    return pd.DataFrame(rows)


def alternate_forms(sessions: pd.DataFrame) -> tuple[float, int]:
    """같은 사람이 겹치지 않는 문제로 푼 1·2차 종합 θ의 상관 (동형 검사 신뢰도)."""
    done = sessions[sessions["completed"] & sessions["theta"].notna()]
    r1 = done[done["round"] == 1].set_index("series_id")["theta"]
    r2 = done[done["round"] == 2].set_index("series_id")["theta"]
    pair = pd.concat([r1, r2], axis=1, join="inner").dropna()
    if len(pair) < 3:
        return float("nan"), len(pair)
    return float(pair.corr().iloc[0, 1]), len(pair)


def deep_usage(sessions: pd.DataFrame) -> pd.DataFrame:
    """심층검사에서 영역마다 몇 문항으로 끝났고, 마지막 오차가 얼마였는지."""
    rows = []
    done = sessions[sessions["completed"] & (sessions["round"] == DEEP_ROUND)]
    for prog in done["progress"]:
        prog = prog or {}
        for d, ids in (prog.get("items") or {}).items():
            est = (prog.get("estimates") or {}).get(d)
            rows.append({"영역": BLUEPRINT[Domain(d)].label, "문항 수": len(ids),
                         "최종 오차(지수)": 15 * est[1] if est else np.nan})
    if not rows:
        return pd.DataFrame(columns=["영역", "응시", "평균 문항 수", "평균 최종 오차(지수)"])
    df = pd.DataFrame(rows)
    return df.groupby("영역", sort=False).agg(**{"응시": ("문항 수", "size"), "평균 문항 수": ("문항 수", "mean"),
                                               "평균 최종 오차(지수)": ("최종 오차(지수)", "mean")}).reset_index()


def round_usage(sessions: pd.DataFrame) -> pd.DataFrame:
    """묶음(같은 사람)마다 어디까지 했는지: 1차만 / 2차까지 / 3차까지 / 심층검사까지."""
    done = sessions[sessions["completed"]]
    if done.empty:
        return pd.DataFrame(columns=["진행", "응시자"])
    last = done.groupby("series_id")["round"].max().value_counts().sort_index()
    return pd.DataFrame({"진행": [f"{round_label(k)}까지" for k in last.index], "응시자": last.values})


def calibrate(responses: pd.DataFrame, items: dict[str, Item], min_n: int = 50) -> dict[str, dict]:
    """응답이 충분한 문항의 난이도 b를 다시 추정한다 (a, c는 고정, 응시자 θ는 현재 추정치).

    결과는 문항 JSON에 irt_b로 넣을 수 있는 제안값이다.
    """
    grid = np.linspace(-3.5, 3.5, 141)
    out = {}
    df = responses[responses["theta"].notna()]
    for item_id, g in df.groupby("item_id"):
        it = items.get(item_id)
        if it is None or it.format is ItemFormat.SYMBOL_CODING or len(g) < min_n:
            continue
        a, b0, c = sc.item_params(it)
        u = g["correct"].astype(float).to_numpy()[:, None]
        th = g["theta"].astype(float).to_numpy()[:, None]
        p = c + (1 - c) / (1 + np.exp(-sc.D * a * (th - grid[None, :])))
        ll = (u * np.log(p) + (1 - u) * np.log(1 - p)).sum(axis=0)
        b = float(grid[ll.argmax()])
        out[item_id] = {"irt_a": a, "irt_b": round(b, 2), "irt_c": c, "n": len(g), "기존_b": round(b0, 2)}
    return out


def session_rows(prog: dict, seed: int, items: dict[str, Item]) -> list[dict]:
    return [r for d in prog["domains"] for r in ex.domain_rows(prog, items, Domain(d), seed)]


def summary(sessions: pd.DataFrame) -> dict:
    started = len(sessions)
    done = sessions[sessions["completed"]]
    dur = (done["completed_at"] - done["started_at"]).dt.total_seconds() / 60 if len(done) else pd.Series(dtype=float)
    return {
        "시작": started, "완료": len(done),
        "완료율": len(done) / started if started else math.nan,
        "첫 응시 완료": int((done["is_first_attempt"] & (done["round"] == 1)).sum()),
        "평균 소요(분)": float(dur.median()) if len(dur) else math.nan,
        "탭 이탈 평균": float(done["focus_lost"].fillna(0).mean()) if len(done) else math.nan,
    }
