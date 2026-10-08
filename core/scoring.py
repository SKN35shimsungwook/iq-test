"""점수 산출: 문항 반응 → 능력 추정치(θ) → LTR Index·백분위·신뢰구간.

규준 데이터가 쌓이기 전(1단계)에는 문항별 예상 정답률(expected_p)로 만든 가정 문항모수를 쓴다.
  - 4지선다·작업기억: 3모수 로지스틱 모형 P(θ) = c + (1−c) / (1 + e^(−1.7·a·(θ−b)))
    a = 1, c = 0.2(4지선다 추측) / 0(작업기억), b는 평균 능력(θ=0)에서 정답률이 expected_p가 되도록 잡는다.
    나중에 파일럿 데이터로 보정한 irt_a/b/c가 문항에 있으면 그 값을 쓴다.
  - 처리속도: 점수를 가정 평균·표준편차로 표준화한 뒤 신뢰도 0.8의 정규 측정 모형으로 θ에 반영한다.
  - θ는 표준정규 사전분포를 둔 EAP(사후 평균)로 추정하고, 사후 표준편차를 표준오차로 쓴다.
실제 응시자가 적을 때는 봇 시뮬레이션 규준(norms/sim_norms.json, scripts/build_sim_norms.py)으로
"같은 단계(1차 / 1~2차 / 1~3차 / +심층)를 마친 가상 응시자 중 위치"를 구해 IQ로 바꾼다.
같은 모드의 첫 응시가 MIN_NORM_N명 이상 쌓이면(2단계) 실제 응시자 분포로 다시 표준화한다.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
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
SIM_NORMS = Path(__file__).resolve().parent.parent / "norms" / "sim_norms.json"

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


def information(item: Item, theta: float) -> float:
    """3모수 문항 정보량 I(θ). 심층검사는 지금 추정한 θ에서 이 값이 가장 큰 문항을 고른다."""
    a, b, c = item_params(item)
    p = c + (1 - c) / (1 + math.exp(-D * a * (theta - b)))
    return (D * a) ** 2 * ((p - c) ** 2 / (1 - c) ** 2) * ((1 - p) / p)


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


@lru_cache(maxsize=1)
def _sim_file() -> dict | None:
    try:
        return json.loads(SIM_NORMS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_sim(mode: str) -> "SimTable | None":
    """봇 시뮬레이션 규준표 (모드별). 파일이 없으면 None → 가정 규준(θ 그대로)."""
    data = _sim_file()
    if not data or mode not in data.get("modes", {}):
        return None
    return SimTable(np.asarray(data["quantile_probs"], dtype=float), data["modes"][mode], int(data["n_per_mode"]))


class SimTable:
    """같은 단계를 마친 봇들의 θ̂ 분포로 θ̂ → z.

    종합: 분위수표로 백분위를 구해 z = Φ⁻¹(백분위) (동백분위 등화).
    영역: 문항이 4~10개라 θ̂가 몇 개 값으로만 나와 백분위가 들쭉날쭉하므로 봇 분포의 평균·표준편차로 표준화 (선형 등화).
    """

    EDGE, BAND = 0.02, 0.10  # 양 끝 2% 바깥은 만점·0점이 몰려 표가 들쭉날쭉 → 2~10%(90~98%) 기울기로 이어 늘린다

    def __init__(self, probs: np.ndarray, table: dict, n: int):
        keep = (probs >= self.EDGE - 1e-9) & (probs <= 1 - self.EDGE + 1e-9)
        self.zs = np.array([NORMAL.inv_cdf(float(p)) for p in probs[keep]])
        self.band = int(np.searchsorted(probs[keep], self.BAND))
        self.total = {stage: np.maximum.accumulate(np.asarray(keys["total"]["quantiles"], dtype=float)[keep])
                      for stage, keys in table.items()}
        self.domain = {stage: {k: (v["mean"], max(v["sd"], 0.1)) for k, v in keys.items() if k != "total"}
                       for stage, keys in table.items()}
        self.n = n

    def z(self, theta: float, stage: str, key: str) -> float | None:
        if key != "total":
            m = self.domain.get(stage, {}).get(key)
            return None if m is None else (theta - m[0]) / m[1]
        q = self.total.get(stage)
        if q is None:
            return None
        zs, b = self.zs, self.band
        if theta <= q[0]:
            return float(zs[0] + (theta - q[0]) * (zs[b] - zs[0]) / max(q[b] - q[0], 1e-6))
        if theta >= q[-1]:
            return float(zs[-1] + (theta - q[-1]) * (zs[-1] - zs[-1 - b]) / max(q[-1] - q[-1 - b], 1e-6))
        return float(np.interp(theta, q, zs))


@dataclass
class Norm:
    """점수 기준: 실제 응시자 분포 → 없으면 봇 시뮬레이션 규준 → 그것도 없으면 가정 규준(θ 그대로)."""
    n: int = 0
    mean: float = 0.0
    sd: float = 1.0
    domain: dict | None = None  # domain value → (mean, sd)
    sim: SimTable | None = None

    @property
    def empirical(self) -> bool:
        return self.n >= MIN_NORM_N

    @property
    def simulated(self) -> bool:
        return not self.empirical and self.sim is not None

    def z(self, theta: float, domain: Domain | None = None, stage: str | None = None) -> float:
        """stage: "1" · "1-2" · "1-3" · "1-3+deep" — 시뮬레이션 규준에서 비교할 단계. None이면 θ 그대로."""
        if not self.empirical:
            if self.sim is not None and stage is not None:
                z = self.sim.z(theta, stage, domain.value if domain else "total")
                if z is not None:
                    return z
            return theta
        if domain is None:
            return (theta - self.mean) / self.sd
        m, s = (self.domain or {}).get(domain.value, (0.0, 1.0))
        return (theta - m) / s


def build_norm(thetas: list[dict], sim: SimTable | None = None) -> Norm:
    """저장된 첫 응시들의 θ 기록({"total": θ, "gf": θ, ...}) → Norm."""
    n = len(thetas)
    if n < MIN_NORM_N:
        return Norm(n=n, sim=sim)

    def stats(vals):
        arr = np.asarray(vals, dtype=float)
        return float(arr.mean()), float(max(arr.std(ddof=1), 0.1))

    mean, sd = stats([t["total"] for t in thetas])
    domains = {}
    for d in DOMAIN_ORDER:
        vals = [t[d.value] for t in thetas if d.value in t]
        if len(vals) >= MIN_NORM_N:
            domains[d.value] = stats(vals)
    return Norm(n=n, mean=mean, sd=sd, domain=domains, sim=sim)


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
