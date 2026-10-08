import math

import numpy as np

import pytest

from core import exam as ex
from core import scoring as sc
from core.item_bank import build_form, load_items
from core.schema import Domain, Mode

ITEMS = load_items()
BY_ID = {it.id: it for it in ITEMS}


def rows_for(form, correct_fn, gs_score=40.0):
    rows = []
    for d, items in form.items():
        for k, it in enumerate(items):
            if d is Domain.GS:
                rows.append({"item_id": it.id, "domain": d.value, "correct": gs_score > 0, "score": gs_score})
            else:
                ok = correct_fn(it, k)
                rows.append({"item_id": it.id, "domain": d.value, "correct": ok, "score": float(ok)})
    return rows


@pytest.mark.parametrize("mode", list(Mode))
def test_scores_are_monotonic_and_bounded(mode):
    form = build_form(ITEMS, 3, mode)
    none = sc.estimate(rows_for(form, lambda it, k: False, 0), BY_ID)[1]
    half = sc.estimate(rows_for(form, lambda it, k: k % 2 == 0), BY_ID)[1]
    every = sc.estimate(rows_for(form, lambda it, k: True, 80), BY_ID)[1]
    assert none.theta < half.theta < every.theta
    assert 40 <= none.index < 85 and 115 < every.index <= 160
    assert 0 < every.se < 1


def test_guess_like_pattern_scores_lower_than_consistent_pattern():
    """같은 개수를 맞혀도, 쉬운 문항을 틀리고 어려운 문항만 맞힌 응답은 찍기로 보고 낮게 추정한다 (3모수 모형)."""
    gf = {Domain.GF: [next(i for i in ITEMS if i.slot == s) for s in
                      ("gf-matrix-2", "gf-analogy-2", "gf-matrix-3", "gf-transform-3")]}
    easy = sc.estimate(rows_for(gf, lambda it, k: it.difficulty == 2), BY_ID)[0][Domain.GF]
    hard = sc.estimate(rows_for(gf, lambda it, k: it.difficulty == 3), BY_ID)[0][Domain.GF]
    assert easy.raw == hard.raw
    assert easy.theta > hard.theta
    assert hard.se > easy.se  # 일관되지 않은 응답은 추정도 덜 확실하다


def test_full_mode_is_more_precise_than_quick():
    half = lambda it, k: k % 2 == 0  # noqa: E731
    q = sc.estimate(rows_for(build_form(ITEMS, 1, Mode.QUICK), half), BY_ID)[1]
    f = sc.estimate(rows_for(build_form(ITEMS, 1, Mode.FULL), half), BY_ID)[1]
    assert f.se < q.se


def test_item_params_reproduce_expected_p_at_average_ability():
    for it in ITEMS[:50]:
        a, b, c = sc.item_params(it)
        p0 = c + (1 - c) / (1 + math.exp(-sc.D * a * (0 - b)))
        assert abs(p0 - min(max(it.expected_p, c + 0.02), 0.98)) < 1e-9


def test_levels_and_percentiles():
    assert sc.level(131) == "매우 우수" and sc.level(100) == "평균" and sc.level(65) == "매우 낮음"
    assert round(sc.percentile(0)) == 50 and round(sc.percentile(1), 1) == 84.1


def test_norm_switches_to_empirical_after_enough_sessions():
    small = sc.build_norm([{"total": 0.5}] * 10)
    assert not small.empirical and small.z(0.5) == 0.5
    thetas = [{"total": 0.5 + (i % 10) * 0.1, "gf": 0.2} for i in range(sc.MIN_NORM_N)]
    norm = sc.build_norm(thetas)
    assert norm.empirical
    assert abs(norm.z(norm.mean)) < 1e-9
    assert norm.z(0.2, Domain.GF) == pytest.approx(0.0)  # 모두 같은 값이면 sd 하한 0.1 적용


def test_strengths_weaknesses_need_clear_gap():
    scores = {Domain.GF: (120, 6), Domain.GC: (100, 6), Domain.GQ: (101, 6), Domain.GV: (85, 6)}
    strong, weak = sc.strengths_weaknesses(scores)
    assert [d for d, _ in strong] == [Domain.GF] and [d for d, _ in weak] == [Domain.GV]
    noisy = {d: (v, 20) for d, (v, _) in scores.items()}  # 오차가 크면 차이로 보지 않음
    assert sc.strengths_weaknesses(noisy) == ([], [])


def test_estimate_accepts_exam_rows():
    form = build_form(ITEMS, 2, Mode.QUICK)
    state = ex.new_exam(form, Mode.QUICK)
    rows = [r for d in form for r in ex.domain_rows(state, BY_ID, d, 2)]
    per, total = sc.estimate(rows, BY_ID)
    assert set(per) == set(form) and total.index < 100


# ---------------------------------------------------------------- 봇 시뮬레이션 규준

@pytest.mark.parametrize("mode", ["quick", "full"])
def test_sim_norm_centered_and_monotonic(mode):
    sim = sc.load_sim(mode)
    assert sim is not None and sim.n >= 10000
    norm = sc.Norm(sim=sim)
    assert norm.simulated
    for stage in ("1", "1-2", "1-3", "1-3+deep"):
        idx = [sc.to_index(norm.z(t, None, stage)) for t in np.linspace(-3, 3, 61)]
        assert all(b >= a for a, b in zip(idx, idx[1:]))  # 능력이 높을수록 IQ도 높다
        median = float(np.median(sim.total[stage]))
        assert sc.to_index(norm.z(median, None, stage)) == pytest.approx(100, abs=1)
        for d in (Domain.GF, Domain.GC):
            m, _ = sim.domain[stage][d.value]
            assert sc.to_index(norm.z(m, d, stage)) == pytest.approx(100, abs=0.1)


def test_sim_norm_spreads_compressed_scores():
    """빠른 검사 1차 영역 점수는 4문항이라 θ̂가 평균 쪽으로 몰린다 → 봇 분포 기준으로 다시 펼친다."""
    norm = sc.Norm(sim=sc.load_sim("quick"))
    assert sc.to_index(norm.z(1.0, Domain.GF, "1")) > sc.to_index(1.0) + 5


def test_empirical_norm_overrides_sim():
    thetas = [{"total": t} for t in np.linspace(-1, 1, 200)]
    norm = sc.build_norm(thetas, sim=sc.load_sim("quick"))
    assert norm.empirical and not norm.simulated
    assert norm.z(norm.mean, None, "1") == pytest.approx(0)


def test_no_stage_falls_back_to_theta():
    norm = sc.Norm(sim=sc.load_sim("quick"))
    assert norm.z(0.7) == 0.7
