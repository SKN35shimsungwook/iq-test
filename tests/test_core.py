import sqlalchemy as sa

from core import db
from core.item_bank import build_form, load_items, validate_blueprint, validate_bank
from core.schema import BLUEPRINT, Domain, Item, ItemFormat, Mode


def make_item(**kw) -> Item:
    base = dict(
        id="gf-01a", domain=Domain.GF, slot="gf-01", format=ItemFormat.MCQ, subtype="matrix",
        difficulty=1, prompt="?", choices=["a", "b", "c", "d"], answer=0,
    )
    return Item(**{**base, **kw})


def test_item_validation_catches_errors():
    assert make_item().validate() == []
    assert make_item(answer=4).validate()
    assert make_item(choices=["a", "a", "b", "c"]).validate()
    assert make_item(difficulty=5).validate()
    assert make_item(id="gq-01a").validate()


def test_bank_files_are_valid():
    errors = [e for e in validate_bank(load_items()) if "필요" not in e]
    assert errors == []


def test_build_form_is_deterministic_per_seed():
    items = [make_item(id=f"gf-01{c}") for c in "ab"] + [make_item(id="gf-02a", slot="gf-02")]
    f1, f2 = build_form(items, 1), build_form(items, 1)
    assert [i.id for i in f1[Domain.GF]] == [i.id for i in f2[Domain.GF]]
    assert [i.slot for i in f1[Domain.GF]] == ["gf-01", "gf-02"]


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


def test_blueprint_respects_type_cap_and_quick_size():
    assert validate_blueprint() == []
    for domain, spec in BLUEPRINT.items():
        quick = spec.slots_for(Mode.QUICK)
        if domain is Domain.GS:
            assert quick == ()
            continue
        assert len(quick) == 4
        assert len({s.subtype for s in quick}) == 4  # 빠른 검사는 영역마다 서로 다른 유형
        assert spec.time_for(Mode.QUICK) or domain is Domain.GWM


def test_generated_forms_use_different_rules():
    items = [it for it in load_items() if it.slot == "gf-01"]
    assert len(items) >= 6
    assert len({str(it.params["rules"]) for it in items}) == len(items)
