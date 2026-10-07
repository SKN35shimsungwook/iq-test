"""결과 화면용 분석 (Streamlit 없이 테스트 가능한 순수 로직).

차수(1·2·3차·심층검사)마다의 평가와, 모든 차수를 합친 최종 결과를 계산한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from core import exam as ex
from core import scoring as sc
from core.schema import BLUEPRINT, DEEP_ROUND, DIFFICULTY_LABELS, Domain, Item, ItemFormat, round_label

GUESS_SEC = 3.0  # 이보다 빨리 낸 오답은 찍었을 가능성이 높다


@dataclass
class Score:
    """θ 추정치를 지수(IQ 척도)로 옮긴 값."""
    theta: float
    se: float
    index: float
    lo: float
    hi: float
    pct: float

    @property
    def margin(self) -> float:
        return (self.hi - self.lo) / 2


def scale(theta: float, se: float, norm: sc.Norm, domain: Domain | None = None) -> Score:
    z = norm.z(theta, domain)
    sd = norm.sd if (domain is None and norm.empirical) else \
        (norm.domain or {}).get(domain.value, (0, 1))[1] if (domain is not None and norm.empirical) else 1.0
    index = sc.to_index(z)
    se_pts = 15 * se / sd
    return Score(theta, se, index, max(index - sc.CI_Z * se_pts, 40), min(index + sc.CI_Z * se_pts, 160),
                 sc.percentile(z))


@dataclass
class RoundData:
    round: int
    seed: int
    progress: dict
    rows: list[dict]
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def label(self) -> str:
        return round_label(self.round)

    @property
    def deep(self) -> bool:
        return self.round == DEEP_ROUND


def load_rounds(series_rows: list[dict], items: dict[str, Item]) -> list[RoundData]:
    """db.series_sessions 결과 → 끝낸 차수들 (차수 순)."""
    out = []
    for r in series_rows:
        prog = r.get("progress")
        if not r.get("completed_at") or not prog:
            continue
        rows = [x for d in prog["domains"] for x in ex.domain_rows(prog, items, Domain(d), r["form_seed"])]
        out.append(RoundData(r["round"], r["form_seed"], prog, rows, r.get("started_at"), r.get("completed_at")))
    return sorted(out, key=lambda x: x.round)


@dataclass
class DomainResult:
    domain: Domain
    score: Score
    correct: int
    n: int
    raw: float
    avg_sec: float | None

    @property
    def label(self) -> str:
        return BLUEPRINT[self.domain].label


@dataclass
class RoundReport:
    total: Score
    domains: list[DomainResult]
    by_level: dict[int, tuple[int, int]] = field(default_factory=dict)  # 난이도 → (맞힌 수, 문항 수)
    correct: int = 0
    n: int = 0
    minutes: float | None = None
    quick_wrong: int = 0      # 3초 안에 낸 오답 (찍기 의심)
    blurs: int = 0


def report(rows: list[dict], items: dict[str, Item], norm: sc.Norm, rd: RoundData | None = None) -> RoundReport:
    per, total = sc.estimate(rows, items)
    domains = []
    for d in sc.DOMAIN_ORDER:
        if d not in per:
            continue
        drows = [r for r in rows if r["domain"] == d.value]
        secs = [r["response_ms"] / 1000 for r in drows if r.get("response_ms")]
        domains.append(DomainResult(
            d, scale(per[d].theta, per[d].se, norm, d),
            correct=sum(1 for r in drows if r["correct"]), n=len(drows), raw=per[d].raw,
            avg_sec=float(np.mean(secs)) if secs and d is not Domain.GS else None))
    by_level: dict[int, list[int]] = {}
    scored = [r for r in rows if items[r["item_id"]].format is not ItemFormat.SYMBOL_CODING]
    for r in scored:
        lv = items[r["item_id"]].difficulty
        by_level.setdefault(lv, [0, 0])
        by_level[lv][0] += int(bool(r["correct"]))
        by_level[lv][1] += 1
    quick_wrong = sum(1 for r in rows if items[r["item_id"]].format is ItemFormat.MCQ and not r["correct"]
                      and r.get("answer") is not None and (r.get("response_ms") or 1e9) < GUESS_SEC * 1000)
    minutes = None
    if rd and rd.started_at and rd.completed_at:
        minutes = (rd.completed_at - rd.started_at).total_seconds() / 60
    return RoundReport(
        total=scale(total.theta, total.se, norm), domains=domains,
        by_level={k: (v[0], v[1]) for k, v in sorted(by_level.items())},
        correct=sum(1 for r in scored if r["correct"]), n=len(scored), minutes=minutes,
        quick_wrong=quick_wrong, blurs=(rd.progress.get("blurs", 0) if rd else 0))


def level_comment(by_level: dict[int, tuple[int, int]]) -> str:
    """난이도별 정답률에서 '어디서부터 막히는지'를 한 문장으로."""
    rates = {lv: c / n for lv, (c, n) in by_level.items() if n}
    if not rates:
        return ""
    parts = " · ".join(f"{DIFFICULTY_LABELS[lv]} {rates[lv]:.0%}" for lv in sorted(rates))
    drop = next((lv for lv in sorted(rates) if rates[lv] < 0.5), None)
    if drop is None:
        tail = "가장 어려운 단계까지 절반 이상 맞혔습니다."
    elif drop == min(rates):
        tail = "가장 쉬운 단계부터 정답률이 절반에 못 미칩니다."
    else:
        tail = f"'{DIFFICULTY_LABELS[drop]}' 단계부터 정답률이 절반 아래로 떨어집니다."
    return f"{parts} — {tail}"


def cumulative(rounds: list[RoundData], items: dict[str, Item], norm: sc.Norm) -> list[tuple[str, Score]]:
    """1차 → 1~2차 → … 처럼 차수를 하나씩 더할 때마다의 점수와 범위."""
    out, acc = [], []
    for rd in rounds:
        acc += rd.rows
        _, total = sc.estimate(acc, items)
        label = rd.label if len(out) == 0 else f"+ {rd.label}"
        out.append((label, scale(total.theta, total.se, norm)))
    return out


def deep_trace(prior_rows: list[dict], deep_rows: list[dict], items: dict[str, Item], norm: sc.Norm) -> list[dict]:
    """심층검사에서 문항을 하나 풀 때마다 영역 점수가 어떻게 좁혀졌는지."""
    out = []
    for d in sc.DOMAIN_ORDER:
        drows = [r for r in deep_rows if r["domain"] == d.value]
        if not drows:
            continue
        prior = [r for r in prior_rows if r["domain"] == d.value]
        for k in range(len(drows) + 1):
            use = prior + drows[:k]
            like = sc._likelihood([items[r["item_id"]] for r in use], [bool(r["correct"]) for r in use])
            theta, se = sc.eap(like)
            s = scale(theta, se, norm, d)
            row = {"영역": BLUEPRINT[d].label, "단계": k, "지수": s.index, "하한": s.lo, "상한": s.hi}
            if k:
                it = items[drows[k - 1]["item_id"]]
                row |= {"난이도": DIFFICULTY_LABELS[it.difficulty], "결과": "정답" if drows[k - 1]["correct"] else "오답"}
            else:
                row |= {"난이도": "1~3차", "결과": "출발"}
            out.append(row)
    return out


def consistency(indices: list[float], margin: float) -> str:
    """차수별 점수가 얼마나 일관된지 한 문장으로."""
    if len(indices) < 2:
        return ""
    spread = max(indices) - min(indices)
    if spread <= margin:
        return (f"차수별 점수 차이가 최대 {spread:.0f}점으로 측정 오차(±{margin:.0f}점) 안에 있어 "
                "결과가 안정적입니다.")
    return (f"차수별 점수 차이가 최대 {spread:.0f}점으로 측정 오차(±{margin:.0f}점)보다 큽니다. "
            "컨디션, 집중도, 문제 유형에 대한 익숙함이 영향을 줬을 수 있습니다.")


LEVEL_GUIDE = [
    (130, 160, "매우 우수", "상위 약 2%"),
    (120, 129, "우수", "상위 약 2~9%"),
    (110, 119, "평균 상", "상위 약 9~25%"),
    (90, 109, "평균", "가운데 약 50%"),
    (80, 89, "평균 하", "하위 약 9~25%"),
    (70, 79, "낮음", "하위 약 2~9%"),
    (40, 69, "매우 낮음", "하위 약 2%"),
]
