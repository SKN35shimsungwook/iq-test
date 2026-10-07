import math

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
    form = build_form(ITEMS, 5, Mode.FULL)
    gf = {Domain.GF: form[Domain.GF]}
    easy = sc.estimate(rows_for(gf, lambda it, k: it.difficulty == 1), BY_ID)[0][Domain.GF]
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
