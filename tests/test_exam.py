import json

from core import exam as ex
from core.item_bank import build_form, load_items
from core.schema import Domain, ItemFormat, Mode

ITEMS = load_items()
BY_ID = {it.id: it for it in ITEMS}


def test_wm_stimulus_expected_answers():
    for it in (i for i in ITEMS if i.domain is Domain.GWM):
        s = ex.wm_stimulus(it, 123)
        assert s == ex.wm_stimulus(it, 123)  # 같은 응시에서는 같은 자극
        if it.format is ItemFormat.SPATIAL_SPAN:
            seq = s["sequence"]
            assert len(seq) == len(set(seq)) == it.params["length"]
            assert max(seq) < it.params["grid"] ** 2
        else:
            d = s["digits"]
            assert len(d) == it.params["length"]
            assert all(a != b for a, b in zip(d, d[1:]))  # 같은 숫자가 연달아 나오지 않음
            mode = it.params["mode"]
            want = {"forward": d, "backward": d[::-1], "sorting": "".join(sorted(d))}[mode]
            assert s["expected"] == want


def test_scoring_by_format():
    mcq = next(i for i in ITEMS if i.format is ItemFormat.MCQ)
    assert ex.score_item(mcq, str(mcq.answer), 1) == (True, 1.0)
    assert ex.score_item(mcq, str((mcq.answer + 1) % 4), 1) == (False, 0.0)
    assert ex.score_item(mcq, None, 1) == (False, 0.0)

    ds = BY_ID["gwm-03a"]
    assert ex.score_item(ds, ex.wm_stimulus(ds, 9)["expected"], 9) == (True, 1.0)

    gs = BY_ID["gs-01a"]
    assert ex.score_item(gs, json.dumps({"correct": 40, "wrong": 3}), 1) == (True, 37.0)
    assert ex.score_item(gs, json.dumps({"correct": 2, "wrong": 5}), 1) == (False, 0.0)


def test_exam_flow_times_out_and_finishes():
    form = build_form(ITEMS, 7, Mode.QUICK)
    state = ex.new_exam(form, Mode.QUICK)
    assert state["domains"] == ["gf", "gc", "gq", "gv", "gwm"]

    ex.start_domain(state, Mode.QUICK, now=1000.0)
    assert state["deadline"] == 1000.0 + 4 * 60
    assert not ex.is_expired(state, now=1100.0)
    assert ex.is_expired(state, now=1000.0 + 4 * 60 - 0.5)  # 브라우저 타이머 오차 허용

    first = state["items"]["gf"][0]
    state["answers"][first] = str(BY_ID[first].answer)
    ex.track_time(state, first, now=1012.5)
    assert state["ms"][first] == 12500

    rows = ex.domain_rows(state, BY_ID, Domain.GF, 7)
    assert len(rows) == 4 and rows[0]["correct"] and sum(r["score"] for r in rows) == 1
    assert rows[1]["answer"] is None and not rows[1]["correct"]
    assert ex.finish_domain(state, rows) is False
    assert state["raw"]["gf"] == 1 and state["stage"] == "intro" and state["d"] == 1

    for _ in range(4):
        d = ex.current_domain(state)
        done = ex.finish_domain(state, ex.domain_rows(state, BY_ID, d, 7))
    assert done


def test_gs_and_wm_have_no_domain_deadline():
    assert ex.domain_time_limit(Domain.GS, Mode.FULL) == 0
    assert ex.domain_time_limit(Domain.GWM, Mode.FULL) == 0
    assert ex.domain_time_limit(Domain.GF, Mode.FULL) == 9 * 60
