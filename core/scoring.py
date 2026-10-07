"""점수 산출: 문항 반응 → 능력 추정치(θ) → LTR Index·백분위·신뢰구간.

규준 데이터가 쌓이기 전(1단계)에는 문항별 예상 정답률(expected_p)로 만든 가정 문항모수를 쓴다.
  - 4지선다·작업기억: 3모수 로지스틱 모형 P(θ) = c + (1−c) / (1 + e^(−1.7·a·(θ−b)))
    a = 1, c = 0.2(4지선다 추측) / 0(작업기억), b는 평균 능력(θ=0)에서 정답률이 expected_p가 되도록 잡는다.
    나중에 파일럿 데이터로 보정한 irt_a/b/c가 문항에 있으면 그 값을 쓴다.
  - 처리속도: 점수를 가정 평균·표준편차로 표준화한 뒤 신뢰도 0.8의 정규 측정 모형으로 θ에 반영한다.
  - θ는 표준정규 사전분포를 둔 EAP(사후 평균)로 추정하고, 사후 표준편차를 표준오차로 쓴다.
같은 모드의 첫 응시가 MIN_NORM_N명 이상 쌓이면(2단계) 실제 응시자 분포로 다시 표준화한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from core.schema import Domain, Item, ItemFormat

D = 1.7
MCQ_GUESS = 0.2
GS_MEAN, GS_SD, GS_RELIABILITY = 40.0, 12.0, 0.8  # 처리속도 90초 (맞힌 수 − 틀린 수) 가정 규준
MIN_NORM_N = 100
GRID = np.linspace(-4, 4, 161)
PRIOR = np.exp(-GRID ** 2 / 2)
NORMAL = NormalDist()
CI_Z = 1.645  # 90% 신뢰구간

DOMAIN_ORDER = [Domain.GF, Domain.GC, Domain.GQ, Domain.GV, Domain.GWM, Domain.GS]
ABILITY_TEXT = {
    Domain.GF: "처음 보는 문제에서 규칙을 찾아내는 힘",
    Domain.GC: "어휘와 낱말 사이의 관계를 이해하는 힘",
    Domain.GQ: "수의 규칙을 찾고 계산으로 문제를 푸는 힘",
    Domain.GV: "도형을 머릿속으로 돌리고 접고 맞춰 보는 힘",
    Domain.GWM: "정보를 잠깐 붙잡아 두고 바꿔 다루는 힘",
    Domain.GS: "단순한 작업을 빠르고 정확하게 해내는 힘",
}
LEVELS = [(130, "매우 우수"), (120, "우수"), (110, "평균 상"), (90, "평균"), (80, "평균 하"), (70, "낮음"), (0, "매우 낮음")]


def item_params(item: Item) -> tuple[float, float, float]:
    if item.irt_b is not None:
        return item.irt_a or 1.0, item.irt_b, item.irt_c or 0.0
    c = MCQ_GUESS if item.format is ItemFormat.MCQ else 0.0
    p = min(max(item.expected_p, c + 0.02), 0.98)
    q = (p - c) / (1 - c)  # 추측을 뺀 정답률
    return 1.0, math.log(1 / q - 1) / D, c


def _likelihood(items: list[Item], correct: list[bool]) -> np.ndarray:
    like = np.ones_like(GRID)
    for it, ok in zip(items, correct):
        a, b, c = item_params(it)
        p = c + (1 - c) / (1 + np.exp(-D * a * (GRID - b)))
        like *= p if ok else 1 - p
    return like


def _speed_likelihood(score: float) -> np.ndarray:
    z = (score - GS_MEAN) / GS_SD
    lam = math.sqrt(GS_RELIABILITY)
    return np.exp(-((z - lam * GRID) ** 2) / (2 * (1 - GS_RELIABILITY)))


def eap(likelihood: np.ndarray) -> tuple[float, float]:
    post = PRIOR * likelihood
    post /= post.sum()
    mean = float((GRID * post).sum())
    return mean, float(math.sqrt(((GRID - mean) ** 2 * post).sum()))


@dataclass
class Estimate:
    theta: float
    se: float
    raw: float
    n_items: int

    @property
    def index(self) -> float:
        return to_index(self.theta)


def to_index(z: float) -> float:
    return min(max(100 + 15 * z, 40.0), 160.0)


def percentile(z: float) -> float:
    return NORMAL.cdf(z) * 100


def level(index: float) -> str:
    return next(label for cut, label in LEVELS if index >= cut)


def estimate(rows: list[dict], items: dict[str, Item]) -> tuple[dict[Domain, Estimate], Estimate]:
    """응답 행(core.exam.domain_rows 형식) → (영역별 추정, 종합 추정).

    종합은 모든 문항을 하나의 일반 능력(g)으로 보고 함께 추정한다.
    """
    per_domain: dict[Domain, Estimate] = {}
    total_like = np.ones_like(GRID)
    total_raw, total_n = 0.0, 0
    for domain in DOMAIN_ORDER:
        drows = [r for r in rows if r["domain"] == domain.value]
        if not drows:
            continue
        if domain is Domain.GS:
            like = _speed_likelihood(drows[0]["score"])
        else:
            like = _likelihood([items[r["item_id"]] for r in drows], [bool(r["correct"]) for r in drows])
        total_like *= like
        raw = sum(r["score"] for r in drows)
        per_domain[domain] = Estimate(*eap(like), raw=raw, n_items=len(drows))
        total_raw += raw if domain is not Domain.GS else 0
        total_n += len(drows) if domain is not Domain.GS else 0
    return per_domain, Estimate(*eap(total_like), raw=total_raw, n_items=total_n)


@dataclass
class Norm:
    """실제 응시자 분포 (θ 척도). 없으면 가정 규준(평균 0, 표준편차 1)."""
    n: int = 0
    mean: float = 0.0
    sd: float = 1.0
    domain: dict | None = None  # domain value → (mean, sd)

    @property
    def empirical(self) -> bool:
        return self.n >= MIN_NORM_N

    def z(self, theta: float, domain: Domain | None = None) -> float:
        if not self.empirical:
            return theta
        if domain is None:
            return (theta - self.mean) / self.sd
        m, s = (self.domain or {}).get(domain.value, (0.0, 1.0))
        return (theta - m) / s


def build_norm(thetas: list[dict]) -> Norm:
    """저장된 첫 응시들의 θ 기록({"total": θ, "gf": θ, ...}) → Norm."""
    n = len(thetas)
    if n < MIN_NORM_N:
        return Norm(n=n)

    def stats(vals):
        arr = np.asarray(vals, dtype=float)
        return float(arr.mean()), float(max(arr.std(ddof=1), 0.1))

    mean, sd = stats([t["total"] for t in thetas])
    domains = {}
    for d in DOMAIN_ORDER:
        vals = [t[d.value] for t in thetas if d.value in t]
        if len(vals) >= MIN_NORM_N:
            domains[d.value] = stats(vals)
    return Norm(n=n, mean=mean, sd=sd, domain=domains)


def strengths_weaknesses(scores: dict[Domain, tuple[float, float]], min_gap: float = 8.0):
    """영역 지수가 본인 평균보다 뚜렷하게 높거나 낮은 영역.

    scores: domain → (지수, 지수 단위 표준오차). 차이가 min_gap 이상이면서 측정오차(80%)보다 커야 한다.
    """
    if len(scores) < 3:
        return [], []
    mean = sum(v for v, _ in scores.values()) / len(scores)
    strong, weak = [], []
    for d, (v, se) in scores.items():
        gap = v - mean
        if abs(gap) >= max(min_gap, 1.28 * se):
            (strong if gap > 0 else weak).append((d, gap))
    strong.sort(key=lambda x: -x[1])
    weak.sort(key=lambda x: x[1])
    return strong, weak
