import json
import random
import zlib

import pytest

from core import figures, gen_spatial
from core.item_bank import ITEMS_DIR, expand_generated

GENERATED = json.loads((ITEMS_DIR / "generated.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("entry", GENERATED, ids=lambda e: f"{e['slot']}-{e['generator']}")
def test_generator_is_valid_across_many_seeds(entry):
    """생성기마다 seed 80개(동형 번호 0~79)로 만들어도 모두 유효하고 정답 위치가 고르게 섞인다."""
    seeds = {**entry, "slot": entry["slot"], "forms": 26}
    items = expand_generated([seeds])
    for i in range(26, 80):  # ID 길이 제한 때문에 26개 이후는 직접 만든다
        svg = {"generator": entry["generator"], "seed": zlib.crc32(f"x{i}".encode()), "form": i,
               "pool_seed": zlib.crc32(entry["slot"].encode()), **entry.get("params", {})}
        items.append(figures.materialize(items[0].__class__(**{**items[0].__dict__, "svg": svg})))
    for it in items:
        assert it.validate() == [], (it.id, it.svg)
    assert {it.answer for it in items} == {0, 1, 2, 3}


def test_generated_forms_are_deterministic():
    a = expand_generated(GENERATED[:3])
    b = expand_generated(GENERATED[:3])
    assert [(x.choices, x.answer) for x in a] == [(y.choices, y.answer) for y in b]


def test_polyomino_is_chiral_and_asymmetric():
    rng = random.Random(0)
    for n in range(5, 10):
        shape = figures._random_polyomino(n, rng)
        rots = {figures._rotate(shape, k) for k in range(4)}
        assert len(rots) == 4
        assert figures._mirror(shape) not in rots
        assert figures._rotate(shape, 4) == shape


def test_cube_fold_finds_opposite_faces():
    cross = frozenset({(1, 0), (0, 1), (1, 1), (2, 1), (3, 1), (1, 2)})
    normals = gen_spatial.fold_cube(cross)
    assert normals[(1, 0)] == tuple(-v for v in normals[(1, 2)])  # 위·아래 날개
    assert normals[(1, 1)] == tuple(-v for v in normals[(3, 1)])  # 한 칸 건너뛴 면
    assert gen_spatial.fold_cube(frozenset({(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)})) is None


def test_paper_fold_unfolds_symmetrically():
    assert gen_spatial._unfold({(3, 0)}, ["L"]) == {(3, 0), (0, 0)}
    assert gen_spatial._unfold({(3, 3)}, ["L", "T"]) == {(3, 3), (0, 3), (3, 0), (0, 0)}


def test_number_rules_have_single_answer():
    """수 행렬·연산 기호: 예시에 맞는 어떤 그럴듯한 규칙으로 풀어도 답이 하나이고, 그 답이 보기에 있다.

    (예시 두 줄이 모두 '첫째 = 둘째'라 a²+b와 a×(b+1)이 구별되지 않던 문제의 재발 방지)
    """
    from core.gen_numeric import NM_RULES, OPS, unambiguous

    entries = [e for e in GENERATED if e["generator"] in ("number_matrix", "operator")]
    items = expand_generated([{**e, "forms": 26} for e in entries])
    for it in items:
        p = it.params
        examples, query = [tuple(x) for x in p["examples"]], tuple(p["query"])
        f = (NM_RULES[p["rule"]][0] if it.svg["generator"] == "number_matrix" else OPS[p["rule"]][0])
        assert all(a != b for a, b in examples + [query]), it.id
        assert unambiguous(f, examples, query), it.id
        assert f(*query) == p["value"] == int(str(it.choices[it.answer]).replace(",", "")), it.id


def test_series_have_single_answer():
    """수열: 보여 준 항을 설명하는 다른 그럴듯한 규칙(다항식·점화식·교대 연산·홀짝 갈래·차이/비율 규칙)이
    모두 같은 다음 수를 예측한다. 규칙 종류(난이도)는 그대로 두고 숫자만 다시 뽑아 맞춘다."""
    from fractions import Fraction

    from core.gen_numeric import series_predictions

    entries = [e for e in GENERATED if e["generator"] == "series"]
    for it in expand_generated([{**e, "forms": 26} for e in entries]):
        p = it.params
        assert series_predictions(p["shown"]) <= {Fraction(p["value"])}, (it.id, p["shown"])
        assert int(str(it.choices[it.answer]).replace(",", "")) == p["value"]


def test_series_checker_catches_ambiguity():
    from core.gen_numeric import series_predictions

    # 1, 2, 4, 7, 11 은 '차이가 1씩 증가'(→16)로 풀리므로, 의도한 답이 다른 값이면 걸러져야 한다
    assert 16 in series_predictions([1, 2, 4, 7, 11])
