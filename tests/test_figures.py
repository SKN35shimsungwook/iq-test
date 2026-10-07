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
