import sqlalchemy as sa

from core import db
from core.item_bank import build_form, load_items, validate_blueprint, validate_bank
from core.schema import BLUEPRINT, SLOTS, Domain, Item, ItemFormat, Mode


def make_item(**kw) -> Item:
    base = dict(
        id="gf-matrix-1a", domain=Domain.GF, slot="gf-matrix-1", format=ItemFormat.MCQ, subtype="matrix",
        difficulty=1, prompt="?", choices=["a", "b", "c", "d"], answer=0,
    )
    return Item(**{**base, **kw})


def test_item_validation_catches_errors():
    assert make_item().validate() == []
    assert make_item(answer=4).validate()
    assert make_item(choices=["a", "a", "b", "c"]).validate()
    assert make_item(difficulty=5).validate()
    assert make_item(id="gq-series-1a").validate()  # 슬롯과 다른 ID
    assert make_item(difficulty=3).validate()  # 슬롯 정의와 다른 난이도


def test_bank_files_are_valid():
    errors = [e for e in validate_bank(load_items()) if "필요" not in e]
    assert errors == []


ITEMS = load_items()


def test_build_form_follows_fixed_plan_and_is_deterministic():
    for mode in Mode:
        f1, f2 = build_form(ITEMS, 1, mode), build_form(ITEMS, 1, mode)
        assert {d: [i.id for i in v] for d, v in f1.items()} == {d: [i.id for i in v] for d, v in f2.items()}
        for domain, form in f1.items():
            assert [it.slot for it in form] == list(BLUEPRINT[domain].form_for(mode))


def test_rounds_never_repeat_items():
    """1·2·3차는 같은 구성이지만 앞 차수에서 본 4지선다 문항은 다시 나오지 않는다."""
    for mode in Mode:
        for start in range(30):
            seen: set[str] = set()
            for r in range(3):
                form = build_form(ITEMS, start * 10 + r, mode, exclude=seen)
                shown = {it.id for v in form.values() for it in v if it.format is ItemFormat.MCQ}
                assert not shown & seen, (mode, start, r)
                seen |= shown


def test_session_roundtrip_and_first_attempt_flag():
    engine = sa.create_engine("sqlite://")
    db.init_db(engine)

    s1 = db.start_session(engine, "client-1", "full", 42, "test")
    db.save_responses(engine, s1, [
        dict(item_id="gf-01a", item_version=1, domain="gf", answer="0", correct=True, score=1, response_ms=1200),
        dict(item_id="gf-02a", item_version=1, domain="gf", answer=None, correct=False, score=0, response_ms=None),
    ])
    db.complete_session(engine, s1, {"gf": 1}, {"gf": 100.0}, 100.0, 50.0)

    s2 = db.start_session(engine, "client-1", "full", 7, "test")  # 같은 브라우저 재응시
    db.complete_session(engine, s2, {"gf": 2}, {"gf": 110.0}, 110.0, 75.0)

    assert db.norm_raw_scores(engine, "full") == [{"gf": 1}]
    assert db.norm_raw_scores(engine, "quick") == []
    rows = db.response_matrix(engine)
    assert {r["item_id"] for r in rows} == {"gf-01a", "gf-02a"}


def test_blueprint_fixed_forms():
    assert validate_blueprint() == []
    for domain, spec in BLUEPRINT.items():
        if domain is Domain.GS:
            assert spec.quick == () and spec.length_for(Mode.FULL) == 1
            continue
        assert spec.length_for(Mode.QUICK) == 4
        assert spec.length_for(Mode.FULL) == (10 if domain is Domain.GF else 8)
        assert set(spec.form_for(Mode.FULL)) <= set(spec.pool)
        levels = [SLOTS[s].difficulty for s in spec.full]
        assert levels[0] == 1 and levels[-1] == 4  # 쉬운 문제로 시작해 매우 어려운 문제로 끝난다


def test_generated_forms_use_different_rules():
    items = [it for it in ITEMS if it.slot == "gf-matrix-1"]
    assert len(items) >= 6
    assert len({str(it.params["rules"]) for it in items}) == len(items)


def test_hand_written_answer_positions_are_balanced():
    from collections import Counter

    written = [it for it in ITEMS if it.domain is Domain.GC or it.subtype == "applied"]
    pos = Counter(it.answer for it in written)
    assert max(pos.values()) - min(pos.values()) <= len(written) * 0.1, pos  # 슬롯당 동형 6개라 완전 균등은 불가
    for it in written:
        assert it.validate() == []  # 정답을 옮긴 뒤에도 verify 식과 일치


def test_save_responses_is_idempotent():
    engine = sa.create_engine("sqlite://")
    db.init_db(engine)
    sid = db.start_session(engine, "c", "quick", 1, "t")
    row = dict(item_id="gf-01a", item_version=1, domain="gf", answer="0", correct=True, score=1, response_ms=10)
    db.save_responses(engine, sid, [row])
    db.save_responses(engine, sid, [row])
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(db.responses)).scalar_one() == 1


def test_progress_roundtrip():
    engine = sa.create_engine("sqlite://")
    db.init_db(engine)
    sid = db.start_session(engine, "c", "full", 5, "t")
    db.save_progress(engine, sid, {"d": 1, "answers": {"gf-01a": "2"}})
    row = db.load_session(engine, sid)
    assert row["progress"]["answers"] == {"gf-01a": "2"} and row["form_seed"] == 5


def test_series_rounds_and_seen_items():
    engine = sa.create_engine("sqlite://")
    db.init_db(engine)
    s1 = db.start_session(engine, "c", "quick", 1, "t")
    db.save_responses(engine, s1, [dict(item_id="gf-matrix-2a", item_version=1, domain="gf", answer="0",
                                        correct=True, score=1, response_ms=1)])
    db.complete_session(engine, s1, {}, {}, 100, 50, thetas={"total": 0.0})
    s2 = db.start_session(engine, "c", "quick", 2, "t", series_id=s1, round_no=2)
    assert [r["round"] for r in db.series_sessions(engine, s1)] == [1, 2]
    assert db.seen_items(engine, s1) == {"gf-matrix-2a"}
    db.complete_session(engine, s2, {}, {}, 110, 70, thetas={"total": 0.5})
    assert db.norm_thetas(engine, "quick") == [{"total": 0.0}]  # 규준은 1라운드만


def test_calibration_file_overrides_assumed_params(tmp_path):
    import json as _json
    import shutil

    from core.item_bank import ITEMS_DIR, load_items as _load
    from core.scoring import item_params

    for f in ITEMS_DIR.glob("*.json"):
        if f.name != "calibration.json":
            shutil.copy(f, tmp_path / f.name)
    (tmp_path / "calibration.json").write_text(_json.dumps({"gc-synonym-1a": {"irt_a": 1.2, "irt_b": -1.5, "irt_c": 0.2}}))
    it = next(i for i in _load(tmp_path) if i.id == "gc-synonym-1a")
    assert item_params(it) == (1.2, -1.5, 0.2)
