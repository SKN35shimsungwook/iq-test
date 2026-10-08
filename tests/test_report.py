from datetime import datetime, timedelta

from core import exam as ex
from core import report as rp
from core import scoring as sc
from core.item_bank import build_form, load_items
from core.schema import DEEP_ROUND, Domain, Mode

ITEMS = load_items()
BY_ID = {it.id: it for it in ITEMS}
NORM = sc.Norm()


def _session(round_no: int, seed: int, seen: set, correct_level: int) -> dict:
    """난이도 correct_level 이하만 맞히는 응시자의 한 차수 세션 (db.series_sessions 행 모양)."""
    state = ex.new_exam(build_form(ITEMS, seed, Mode.QUICK, exclude=seen), Mode.QUICK)
    for ids in state["items"].values():
        for i in ids:
            it = BY_ID[i]
            if it.format.value == "mcq":
                state["answers"][i] = str(it.answer if it.difficulty <= correct_level else (it.answer + 1) % 4)
                state["ms"][i] = 12000
    t0 = datetime(2026, 10, 7, 10, 0)
    return {"round": round_no, "form_seed": seed, "progress": state, "completed_at": t0 + timedelta(minutes=14),
            "started_at": t0}


def _series():
    seen, out = set(), []
    for r in (1, 2, 3):
        s = _session(r, 40 + r, seen, correct_level=2)
        seen |= {i for ids in s["progress"]["items"].values() for i in ids}
        out.append(s)
    return out


def test_round_report_fields():
    rounds = rp.load_rounds(_series(), ITEMS and BY_ID)
    assert [r.round for r in rounds] == [1, 2, 3] and rounds[0].label == "1차 검증"
    rep = rp.report(rounds[0].rows, BY_ID, NORM, rounds[0])
    assert rep.minutes == 14
    assert rep.n == 20  # 빠른 검사 5개 영역 × 4문항 (작업기억은 미응답으로 포함, 처리속도 없음)
    # 쉬움·보통만 맞히는 응시자: 난이도별 정답률이 3단계부터 떨어진다
    lv = {k: c / n for k, (c, n) in rep.by_level.items()}
    assert lv[1] > lv[3] and lv[4] == 0
    assert "어려움" in rp.level_comment(rep.by_level)
    assert rep.total.lo < rep.total.index < rep.total.hi


def test_cumulative_range_shrinks():
    rounds = rp.load_rounds(_series(), BY_ID)
    cum = rp.cumulative(rounds, BY_ID, NORM)
    assert [c[0] for c in cum] == ["1차 검증", "+ 2차 검증", "+ 3차 검증"]
    margins = [c[1].margin for c in cum]
    assert margins[0] > margins[1] > margins[2]


def test_deep_trace_starts_from_prior_and_narrows():
    rounds = rp.load_rounds(_series(), BY_ID)
    prior = [r for rd in rounds for r in rd.rows]
    seen = {r["item_id"] for r in prior}
    state = ex.new_deep_exam(prior, seen, Mode.QUICK)
    state["d"] = 0
    while (iid := ex.deep_next(state, BY_ID, 9)) is not None:
        it = BY_ID[iid]
        state["answers"][iid] = str(it.answer if it.difficulty <= 2 else (it.answer + 1) % 4)
    deep_rows = ex.domain_rows(state, BY_ID, Domain.GF, 9)
    trace = rp.deep_trace(prior, deep_rows, BY_ID, NORM)
    gf = [t for t in trace if t["영역"] == "유동추론"]
    assert gf[0]["단계"] == 0 and gf[0]["결과"] == "출발" and len(gf) == len(deep_rows) + 1
    assert (gf[-1]["상한"] - gf[-1]["하한"]) < (gf[0]["상한"] - gf[0]["하한"])


def test_consistency_message():
    assert "안정적" in rp.consistency([101, 104, 103], margin=6)
    assert "큽니다" in rp.consistency([95, 110], margin=6)
    assert rp.consistency([100], margin=6) == ""


def test_scale_and_levels():
    s = rp.scale(0.0, 0.3, NORM)
    assert s.index == 100 and round(s.pct) == 50
    assert round(s.margin, 1) == round(sc.CI_Z * 15 * 0.3, 1)
    assert DEEP_ROUND == 4


def test_stage_names():
    assert [rp.stage(n) for n in (1, 2, 3)] == ["1", "1-2", "1-3"]
    assert rp.stage(3, deep=True) == "1-3+deep"


def test_scale_range_contains_index_with_sim_norm():
    norm = sc.Norm(sim=sc.load_sim("full"))
    for theta in (-2.5, -0.5, 0, 1.2, 2.8):
        s = rp.scale(theta, 0.3, norm, stage="1-2")
        assert 40 <= s.lo <= s.index <= s.hi <= 160
