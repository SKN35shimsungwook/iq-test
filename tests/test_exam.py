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

    ds = BY_ID["gwm-backward-1a"]
    assert ex.score_item(ds, ex.wm_stimulus(ds, 9)["expected"], 9) == (True, 1.0)

    gs = BY_ID["gs-symbol_coding-2a"]
    assert ex.score_item(gs, json.dumps({"correct": 40, "wrong": 3}), 1) == (True, 37.0)
    assert ex.score_item(gs, json.dumps({"correct": 2, "wrong": 5}), 1) == (False, 0.0)


def test_round_exam_flow_times_out_and_finishes():
    form = build_form(ITEMS, 7, Mode.QUICK)
    state = ex.new_exam(form, Mode.QUICK)
    assert state["domains"] == ["gf", "gc", "gq", "gv", "gwm"] and state["kind"] == "round"

    ex.start_domain(state, Mode.QUICK, now=1000.0)
    assert state["deadline"] == 1000.0 + 4 * 60
    assert not ex.is_expired(state, now=1100.0)
    assert ex.is_expired(state, now=1000.0 + 4 * 60 - 0.5)  # 브라우저 타이머 오차 허용

    ids = state["items"]["gf"]
    assert [BY_ID[i].difficulty for i in ids] == [1, 2, 3, 4]
    for i in ids[:2]:
        state["answers"][i] = str(BY_ID[i].answer)
    ex.track_time(state, ids[0], now=1012.5)
    assert state["ms"][ids[0]] == 12500

    rows = ex.domain_rows(state, BY_ID, Domain.GF, 7)
    assert len(rows) == 4 and sum(r["score"] for r in rows) == 2
    assert ex.finish_domain(state, rows) is False
    assert state["raw"]["gf"] == 2 and state["stage"] == "intro" and state["d"] == 1
    for _ in range(4):
        d = ex.current_domain(state)
        done = ex.finish_domain(state, ex.domain_rows(state, BY_ID, d, 7))
    assert done


def _prior(theta_correct: bool) -> tuple[list[dict], set[str]]:
    """1~3차를 모두 맞혔거나 모두 틀린 응답 기록."""
    rows, seen = [], set()
    for r in range(3):
        form = build_form(ITEMS, 100 + r, Mode.QUICK, exclude=seen)
        for d, its in form.items():
            for it in its:
                rows.append({"item_id": it.id, "domain": d.value, "correct": theta_correct,
                             "score": float(theta_correct)})
                seen.add(it.id)
    return rows, seen


def test_deep_exam_targets_ability_and_stops():
    from core.schema import DEEP_MAX_ITEMS, DEEP_MIN_ITEMS

    for strong in (True, False):
        prior, seen = _prior(strong)
        state = ex.new_deep_exam(prior, seen, Mode.QUICK)
        assert state["kind"] == "deep" and "gs" not in state["domains"]
        ex.start_domain(state, Mode.QUICK, now=0.0)
        assert state["deadline"] == DEEP_MAX_ITEMS * 60  # 유동추론
        picked = []
        while (iid := ex.deep_next(state, BY_ID, 5)) is not None:
            it = BY_ID[iid]
            assert iid not in seen  # 앞 차수에서 본 4지선다는 다시 나오지 않음
            picked.append(it.difficulty)
            state["answers"][iid] = str(it.answer if strong else (it.answer + 1) % 4)
        assert DEEP_MIN_ITEMS <= len(picked) <= DEEP_MAX_ITEMS
        avg = sum(picked) / len(picked)
        assert avg >= 3 if strong else avg <= 2, (strong, picked)  # 잘하면 어려운 문제, 못하면 쉬운 문제
        theta, _ = state["estimates"]["gf"]
        assert theta > 1 if strong else theta < -1


def test_item_information_peaks_near_difficulty():
    from core import scoring as sc

    it = next(i for i in ITEMS if i.slot == "gf-matrix-3")
    _, b, _ = sc.item_params(it)
    assert sc.information(it, b) > sc.information(it, b - 2)
    assert sc.information(it, b) > sc.information(it, b + 2)


def test_gs_and_wm_have_no_domain_deadline():
    assert ex.domain_time_limit(Domain.GS, Mode.FULL) == 0
    assert ex.domain_time_limit(Domain.GWM, Mode.FULL) == 0
    assert ex.domain_time_limit(Domain.GF, Mode.FULL) == 9 * 60


def test_aborted_speed_block_scores_zero():
    assert ex.score_item(BY_ID["gs-symbol_coding-2a"], ex.ABORTED_GS, 1) == (False, 0.0)
    assert ex.score_item(BY_ID["gwm-forward-1a"], "", 1) == (False, 0.0)
