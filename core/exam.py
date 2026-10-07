"""응시 진행 상태와 채점 (Streamlit 없이 테스트 가능한 순수 로직).

진행 상태는 dict 하나로 st.session_state["exam"]에 보관한다.
"""

from __future__ import annotations

import json
import random
import time

from core.schema import BLUEPRINT, Domain, Item, ItemFormat, Mode

SYMBOLS = ["◆", "▲", "●", "■", "★", "✚", "◐", "♥", "☾"]
EXPIRY_SLACK_SEC = 1.0  # 브라우저 타이머가 서버보다 조금 먼저 끝나는 차이를 흡수
ABORTED_GS = json.dumps({"correct": 0, "wrong": 0, "aborted": True})  # 진행 중 새로고침한 처리속도 블록


def new_exam(form: dict[Domain, list[Item]], mode: Mode) -> dict:
    return {
        "domains": [d.value for d in form],
        "items": {d.value: [it.id for it in items] for d, items in form.items()},
        "d": 0,            # 현재 영역 인덱스
        "stage": "intro",  # intro | items
        "i": 0,            # 현재 문항 인덱스
        "answers": {},     # item_id → 응답 문자열 (미응답이면 없음)
        "ms": {},          # item_id → 누적 응답 시간(ms)
        "deadline": None,  # 영역 마감 시각 (epoch 초)
        "entered": None,   # 현재 문항을 보기 시작한 시각
        "blurs": 0,        # 탭·창 이탈 횟수
        "started": [],     # 제시가 시작된 작업기억·처리속도 문항 (새로고침 재시청 방지)
        "raw": {},         # domain → 원점수
        "mode": mode.value,
    }


def current_domain(exam: dict) -> Domain:
    return Domain(exam["domains"][exam["d"]])


def domain_time_limit(domain: Domain, mode: Mode) -> int:
    """영역 제한시간(초). 처리속도는 컴포넌트가 직접 시간을 재므로 0."""
    return 0 if domain is Domain.GS else BLUEPRINT[domain].time_for(mode)


def start_domain(exam: dict, mode: Mode, now: float | None = None) -> None:
    now = time.time() if now is None else now
    limit = domain_time_limit(current_domain(exam), mode)
    exam.update(stage="items", i=0, entered=now, deadline=now + limit if limit else None)


def is_expired(exam: dict, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    return exam["deadline"] is not None and now >= exam["deadline"] - EXPIRY_SLACK_SEC


def track_time(exam: dict, item_id: str, now: float | None = None) -> None:
    """지금 보고 있던 문항에 머문 시간을 더하고 시계를 다시 맞춘다."""
    now = time.time() if now is None else now
    if exam["entered"] is not None:
        exam["ms"][item_id] = exam["ms"].get(item_id, 0) + int((now - exam["entered"]) * 1000)
    exam["entered"] = now


# ---------------------------------------------------------------- 작업기억·처리속도 자극

def _rng(seed: int, item_id: str) -> random.Random:
    return random.Random(f"{seed}:{item_id}")


def wm_stimulus(item: Item, seed: int) -> dict:
    """응시마다 새로 정해지는 자극과 기대 정답."""
    rng = _rng(seed, item.id)
    p = item.params
    if item.format is ItemFormat.SPATIAL_SPAN:
        seq = rng.sample(range(p["grid"] ** 2), p["length"])
        return {"sequence": seq, "expected": ",".join(map(str, seq))}
    if p["mode"] == "sorting":
        digits = rng.sample(range(1, 10), p["length"])  # 정렬은 중복 없이
    else:
        digits = [rng.randint(1, 9)]
        while len(digits) < p["length"]:
            d = rng.randint(1, 9)
            if d != digits[-1]:
                digits.append(d)
    shown = "".join(map(str, digits))
    expected = {"forward": shown, "backward": shown[::-1],
                "sorting": "".join(map(str, sorted(digits)))}[p["mode"]]
    return {"digits": shown, "expected": expected}


def gs_stimulus(item: Item, seed: int) -> dict:
    rng = _rng(seed, item.id)
    symbols = rng.sample(SYMBOLS, item.params.get("symbols", 9))
    seq, prev = [], -1
    for _ in range(300):
        n = rng.randrange(len(symbols))
        while n == prev:
            n = rng.randrange(len(symbols))
        seq.append(n)
        prev = n
    return {"symbols": symbols, "sequence": seq}


# ---------------------------------------------------------------- 채점

def score_item(item: Item, answer: str | None, seed: int) -> tuple[bool, float]:
    """(정답 여부, 점수). 처리속도는 (맞힌 수 − 틀린 수)를 점수로 쓴다."""
    if answer is None:
        return False, 0.0
    if item.format is ItemFormat.MCQ:
        ok = answer == str(item.answer)
        return ok, float(ok)
    if item.format in (ItemFormat.DIGIT_SPAN, ItemFormat.SPATIAL_SPAN):
        ok = answer == wm_stimulus(item, seed)["expected"]
        return ok, float(ok)
    if item.format is ItemFormat.SYMBOL_CODING:
        r = json.loads(answer)
        s = max(0, r["correct"] - r["wrong"])
        return s > 0, float(s)
    raise ValueError(item.format)


def domain_rows(exam: dict, items: dict[str, Item], domain: Domain, seed: int) -> list[dict]:
    rows = []
    for item_id in exam["items"][domain.value]:
        item = items[item_id]
        answer = exam["answers"].get(item_id)
        correct, score = score_item(item, answer, seed)
        rows.append({"item_id": item_id, "item_version": item.version, "domain": domain.value,
                     "answer": answer, "correct": correct, "score": score,
                     "response_ms": exam["ms"].get(item_id)})
    return rows


def finish_domain(exam: dict, rows: list[dict]) -> bool:
    """영역 원점수를 기록하고 다음 영역으로. 모든 영역이 끝났으면 True."""
    domain = current_domain(exam)
    exam["raw"][domain.value] = sum(r["score"] for r in rows)
    exam.update(d=exam["d"] + 1, stage="intro", i=0, deadline=None, entered=None)
    return exam["d"] >= len(exam["domains"])
