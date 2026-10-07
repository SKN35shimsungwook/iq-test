"""유동추론 도형 생성기: 도형 시퀀스, 도형 유추, 다른 도형 찾기, 도형 변환 기호.

셀(도형 묶음) 표현과 그리기는 figures.py의 행렬 생성기와 공유한다.
"""

from __future__ import annotations

import random
from dataclasses import replace
from itertools import combinations

from core.figures import (CELL, DIR_KO, SHAPE_KO, SHAPES, TOPIC_KO, VALUES, _cell_body, _cell_svg,
                          _describe, _frame, _svg, pick_variant)
from core.schema import Item

Cell = dict


def _key(c: Cell) -> tuple:
    return tuple(sorted(c.items()))


def _shuffle(options: list[Cell], rng: random.Random) -> tuple[list[str], int]:
    """options[0]이 정답. 중복이 없는지 확인하고 섞어서 (SVG 보기, 정답 인덱스)."""
    assert len({_key(o) for o in options}) == len(options) == 4, options
    order = rng.sample(range(4), 4)
    return [_cell_svg(options[i]) for i in order], order.index(0)


def _balanced(answer: Cell, alts: dict[str, object]) -> list[Cell]:
    """각 속성의 정답 값이 보기 4개 중 정확히 2개에 나오는 균형 보기 (첫 번째가 정답)."""
    attrs = list(alts)
    patterns = [(0, 0), (1, 0), (0, 1), (1, 1)] if len(attrs) == 2 else \
        [(0, 0, 0), (1, 1, 0), (1, 0, 1), (0, 1, 1)]
    out = []
    for pat in patterns:
        cell = dict(answer)
        for a, flip in zip(attrs, pat):
            if flip:
                cell[a] = alts[a]
        out.append(cell)
    return out


def _row_svg(cells: list[Cell | None], gap: int = 10) -> str:
    """셀을 가로로 나열. None은 물음표 칸."""
    body = ""
    for i, c in enumerate(cells):
        x = i * (CELL + gap)
        if c is None:
            body += _frame(x, 0, dashed=True) + _qmark(x, 0)
        else:
            body += _frame(x, 0) + _cell_body(c, x, 0)
    return _svg(len(cells) * (CELL + gap) - gap, CELL, body)


def _qmark(x: float, y: float) -> str:
    return (f'<text x="{x + 50}" y="{y + 64}" text-anchor="middle" font-size="44" font-family="sans-serif" '
            f'font-weight="700" fill="#6b7280">?</text>')


def _arrow(x1: float, x2: float, y: float = CELL / 2) -> str:
    return (f'<line x1="{x1}" y1="{y}" x2="{x2 - 8}" y2="{y}" stroke="#6b7280" stroke-width="2.5"/>'
            f'<polygon points="{x2},{y} {x2 - 10},{y - 6} {x2 - 10},{y + 6}" fill="#6b7280"/>')


def _base_cell(rng: random.Random, arrow: bool) -> Cell:
    return {"shape": "arrow" if arrow else rng.choice(SHAPES), "count": rng.choice([1, 2, 3]),
            "fill": rng.choice(VALUES["fill"]), "rot": 0}


# ---------------------------------------------------------------- 도형 시퀀스

SEQ_LEVELS = {
    1: [{"rot": 90}, {"rot": 45}, {"fill": 3}, {"shape": 3}, {"count": 3}, {"shape": 2}],
    2: [{"rot": 90, "fill": 2}, {"rot": -45, "count": 3}, {"shape": 3, "fill": 2},
        {"shape": 2, "count": 3}, {"fill": 3, "count": 2}, {"rot": 45, "fill": 3}],
    3: [{"rot": 90, "fill": 3, "count": 2}, {"rot": -90, "fill": 2, "count": 3}, {"shape": 3, "fill": 2, "count": 3},
        {"rot": 45, "count": 3, "fill": 2}, {"shape": 2, "fill": 3, "count": 4}, {"rot": -45, "fill": 3, "count": 4}],
    # "acc": 도는 각도가 한 칸마다 45°씩 커짐, count 4: a, a+1, a+2, a+1로 오르내림
    4: [{"rot": "acc", "fill": 3}, {"rot": "acc", "count": 3}, {"rot": "acc", "fill": 2, "count": 3},
        {"count": 4, "shape": 3, "fill": 2}, {"count": 4, "fill": 3}, {"rot": "acc", "count": 4}],
}
FRAMES = 6  # 5칸 제시 + 정답 1칸


def _seq_values(attr: str, rule: int, rng: random.Random) -> list:
    if attr == "rot":
        start = rng.choice([0, 90, 180, 270])
        if rule == "acc":
            return [(start + 45 * i * (i + 1) // 2) % 360 for i in range(FRAMES + 1)]
        return [(start + rule * i) % 360 for i in range(FRAMES + 1)]
    if attr == "count" and rule == 4:
        a = rng.randint(1, 3)
        return [[a, a + 1, a + 2, a + 1][i % 4] for i in range(FRAMES + 1)]
    pool = [v for v in VALUES[attr] if attr != "count" or v <= 4]
    cycle = rng.sample(pool, rule)
    return [cycle[i % rule] for i in range(FRAMES + 1)]


def _seq_text(attr: str, rule: int) -> str:
    if attr == "rot" and rule == "acc":
        return "화살표가 도는 각도가 45°, 90°, 135°, …로 한 칸마다 45°씩 커집니다."
    if attr == "count" and rule == 4:
        return "개수가 하나씩 늘었다가 다시 줄어드는 흐름(예: 1, 2, 3, 2, 1, 2, …)이 반복됩니다."
    if attr == "rot":
        way = "시계" if rule > 0 else "반시계"
        return f"화살표가 한 칸마다 {way} 방향으로 {abs(rule)}°씩 돕니다."
    return f"{TOPIC_KO[attr]} {rule}가지가 차례로 반복됩니다."


def sequence_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    rules: dict[str, int] = pick_variant(spec, SEQ_LEVELS[spec["level"]])
    base = _base_cell(rng, arrow="rot" in rules)
    series = {a: _seq_values(a, r, rng) for a, r in rules.items()}
    frames = [{**base, **{a: series[a][i] for a in rules}} for i in range(FRAMES + 1)]
    answer = frames[FRAMES - 1]

    alts = {}
    for a in rules:
        cands = [v for v in (frames[FRAMES - 2][a], frames[FRAMES][a]) if v != answer[a]]
        alts[a] = rng.choice(cands)
    if len(alts) == 1:  # 규칙이 하나면 고정 속성 하나를 짝으로 균형 설계
        partner = "fill" if "fill" not in rules else "count"
        alts[partner] = rng.choice([v for v in VALUES[partner] if v != base[partner]])
    choices, idx = _shuffle(_balanced(answer, alts), rng)
    explanation = " ".join(_seq_text(a, r) for a, r in rules.items()) + f" 따라서 다음은 '{_describe(answer)}'입니다."
    return replace(item, stem_svg=_row_svg(frames[:FRAMES - 1] + [None]), choices=choices, answer=idx,
                   explanation=explanation, params={**item.params, "rules": rules})


# ---------------------------------------------------------------- 도형 유추 (A : B = C : ?)

TRANSFORMS = {
    # 이름: (속성, 변환, 설명)
    "rot90": ("rot", lambda c: {**c, "rot": (c["rot"] + 90) % 360}, "시계 방향으로 90° 돌립니다"),
    "rot180": ("rot", lambda c: {**c, "rot": (c["rot"] + 180) % 360}, "180° 돌립니다"),
    "rot270": ("rot", lambda c: {**c, "rot": (c["rot"] + 270) % 360}, "반시계 방향으로 90° 돌립니다"),
    "invert": ("fill", lambda c: {**c, "fill": {"white": "black", "black": "white"}[c["fill"]]},
               "흰색과 검은색을 바꿉니다"),
    "count_up": ("count", lambda c: {**c, "count": c["count"] + 1}, "개수를 하나 늘립니다"),
    "double": ("count", lambda c: {**c, "count": c["count"] * 2}, "개수를 두 배로 늘립니다"),
}
ANALOGY_LEVELS = {
    1: [["invert"], ["count_up"], ["rot180"], ["invert"], ["count_up"], ["rot90"]],  # A와 C가 같은 모양
    2: [["rot90"], ["invert"], ["count_up"], ["rot180"], ["double"], ["rot270"]],
    3: [["rot90", "invert"], ["count_up", "invert"], ["double", "rot180"], ["rot270", "count_up"],
        ["rot90", "double"], ["rot180", "invert"]],
    4: [["rot90", "invert", "count_up"], ["rot270", "invert", "double"], ["rot180", "count_up", "invert"],
        ["rot90", "double", "invert"], ["rot270", "count_up", "invert"], ["rot180", "double", "invert"]],
}


def _apply(cell: Cell, names: list[str]) -> Cell | None:
    for n in names:
        attr, f, _ = TRANSFORMS[n]
        if attr == "fill" and cell["fill"] == "gray":
            return None
        cell = f(cell)
        if not 1 <= cell["count"] <= 5:
            return None
    return cell


def _transform_combos() -> list[list[str]]:
    singles = [[n] for n in TRANSFORMS]
    pairs = [[a, b] for a, b in combinations(TRANSFORMS, 2) if TRANSFORMS[a][0] != TRANSFORMS[b][0]]
    triples = [list(t) for t in combinations(TRANSFORMS, 3) if len({TRANSFORMS[n][0] for n in t}) == 3]
    return singles + pairs + triples


def analogy_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    names: list[str] = pick_variant(spec, ANALOGY_LEVELS[spec["level"]])
    arrow = any(TRANSFORMS[n][0] == "rot" for n in names)
    used = {TRANSFORMS[n][0] for n in names}
    decoys = [d for d in TRANSFORMS if TRANSFORMS[d][0] not in used and (arrow or TRANSFORMS[d][0] != "rot")]

    for _ in range(1000):
        a, c = _base_cell(rng, arrow), _base_cell(rng, arrow)
        if spec["level"] == 1:
            c["shape"] = a["shape"]
        a["fill"], c["fill"] = rng.choice(["white", "black"]), rng.choice(["white", "black"])
        if arrow:
            a["rot"], c["rot"] = rng.choice([0, 90, 180, 270]), rng.choice([0, 90, 180, 270])
        b, ans = _apply(a, names), _apply(c, names)
        if b is None or ans is None or _key(a) == _key(c):
            continue
        # A→B를 설명하는 다른 변환 조합이 C에 다른 결과를 내면 모호하므로 다시 뽑는다
        rivals = [m for m in _transform_combos() if _apply(a, m) is not None and _key(_apply(a, m)) == _key(b)]
        if any(_apply(c, m) is None or _key(_apply(c, m)) != _key(ans) for m in rivals):
            continue
        if len(names) == 3:  # 변환 하나씩 빠뜨린 결과가 오답
            options = [ans, *(_apply(c, [n for n in names if n != skip]) for skip in names)]
        elif len(names) == 2:
            options = [ans, _apply(c, names[:1]), _apply(c, names[1:]), c]
        else:
            d = rng.choice(decoys)
            options = [ans, c, _apply(c, [d]), _apply(c, [names[0], d])]
        if any(o is None for o in options) or len({_key(o) for o in options}) < 4:
            continue
        break
    else:
        raise RuntimeError(f"[{item.id}] 도형 유추 생성 실패")

    gap, arr = 10, 44
    xs = [0, CELL + arr, 2 * CELL + arr + 40, 3 * CELL + 2 * arr + 40]
    body = ""
    for x, cell in zip(xs, [a, b, c, None]):
        body += _frame(x, 0, dashed=cell is None) + (_qmark(x, 0) if cell is None else _cell_body(cell, x, 0))
    body += _arrow(xs[0] + CELL + gap, xs[1] - gap / 2) + _arrow(xs[2] + CELL + gap, xs[3] - gap / 2)
    mid = xs[1] + CELL + 20
    body += (f'<circle cx="{mid}" cy="{CELL / 2 - 10}" r="4" fill="#6b7280"/>'
             f'<circle cx="{mid}" cy="{CELL / 2 + 10}" r="4" fill="#6b7280"/>')
    choices, idx = _shuffle(options, rng)
    rule = ", 그리고 ".join(TRANSFORMS[n][2] for n in names)
    return replace(item, stem_svg=_svg(xs[3] + CELL, CELL, body), choices=choices, answer=idx,
                   explanation=f"왼쪽 그림은 {rule}. 같은 변화를 세 번째 그림에 적용하면 '{_describe(ans)}'입니다.",
                   params={**item.params, "transforms": names})


# ---------------------------------------------------------------- 다른 도형 찾기

COLOR_KO = {"white": "흰색", "gray": "회색", "black": "검은색"}
CORNERS = {"triangle": 3, "square": 4, "pentagon": 5}
ODD_FAMILIES = {
    "shape": lambda c: c["shape"],
    "fill": lambda c: c["fill"],
    "count": lambda c: c["count"],
    "rot": lambda c: c["rot"] if c["shape"] == "arrow" else None,
    "parity": lambda c: c["count"] % 2,
    "corners": lambda c: CORNERS.get(c["shape"]) == c["count"],
    # 두 속성의 관계: 홀수 개면 검은색 / 세로(위·아래)를 향하면 검은색
    "fill_parity": lambda c: None if c["fill"] == "gray" else (c["fill"] == "black") == (c["count"] % 2 == 1),
    "rot_fill": lambda c: None if c["shape"] != "arrow" or c["fill"] == "gray"
    else (c["fill"] == "black") == (c["rot"] in (0, 180)),
}
ODD_LEVELS = {1: ["shape", "fill", "count", "rot", "shape", "fill"],
              2: ["parity", "corners", "parity", "corners", "rot", "count"],
              3: ["fill_parity", "rot_fill", "fill_parity", "rot_fill", "fill_parity", "rot_fill"]}


def _odd_index(cells: list[Cell], fam: str) -> int | None:
    """그 기준으로 셋이 같고 하나만 다르면 그 하나의 인덱스."""
    keys = [ODD_FAMILIES[fam](c) for c in cells]
    if None in keys:
        return None
    for i in range(4):
        rest = keys[:i] + keys[i + 1:]
        if len(set(rest)) == 1 and keys[i] != rest[0]:
            return i
    return None


def _odd_text(fam: str, cells: list[Cell], odd: int) -> str:
    c = cells[(odd + 1) % 4]
    return {
        "shape": f"나머지 셋은 모두 {SHAPE_KO[c['shape']]}입니다.",
        "fill": f"나머지 셋은 모두 {COLOR_KO[c['fill']]}입니다.",
        "count": f"나머지 셋은 모두 {c['count']}개입니다.",
        "rot": f"나머지 셋은 화살표가 모두 {DIR_KO[c['rot']]} 방향을 향합니다.",
        "parity": f"나머지 셋은 개수가 모두 {'홀수' if c['count'] % 2 else '짝수'}입니다.",
        "corners": "나머지 셋은 도형의 개수가 꼭짓점 수와 같습니다 (삼각형 3개, 사각형 4개, 오각형 5개).",
        "fill_parity": "나머지 셋은 '개수가 홀수면 검은색, 짝수면 흰색' 규칙을 따릅니다.",
        "rot_fill": "나머지 셋은 '위·아래를 향하면 검은색, 왼쪽·오른쪽을 향하면 흰색' 규칙을 따릅니다.",
    }[fam]


def _random_cell(rng: random.Random, fam: str) -> Cell:
    shape = "arrow" if fam in ("rot", "rot_fill") else rng.choice(list(CORNERS) if fam == "corners" else SHAPES)
    count = CORNERS[shape] if fam == "corners" else rng.randint(1, 4)
    fills = ["white", "black"] if fam in ("fill_parity", "rot_fill") else VALUES["fill"]
    return {"shape": shape, "count": count, "fill": rng.choice(fills),
            "rot": rng.choice([0, 90, 180, 270]) if shape == "arrow" else 0}


def odd_one_out_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    fam = pick_variant(spec, ODD_LEVELS[spec["level"]])
    for _ in range(5000):
        cells = [_random_cell(rng, fam) for _ in range(4)]
        if fam in ("shape", "fill", "count", "rot"):
            shared = ODD_FAMILIES[fam](cells[0]) if fam != "rot" else cells[0]["rot"]
            for c in cells[1:]:
                c[fam] = shared
            others = [v for v in VALUES[fam] if v != shared and (fam != "count" or v <= 4)]
            cells[3][fam] = rng.choice(others)
            if fam == "shape" and cells[3]["shape"] == "arrow":
                continue
        elif fam == "parity":
            par = rng.choice([0, 1])
            for c in cells[:3]:
                c["count"] = rng.choice([n for n in range(1, 6) if n % 2 == par])
            cells[3]["count"] = rng.choice([n for n in range(1, 6) if n % 2 != par])
        elif fam == "fill_parity":
            for c in cells:
                c["fill"] = "black" if c["count"] % 2 else "white"
            cells[3]["fill"] = "white" if cells[3]["fill"] == "black" else "black"
        elif fam == "rot_fill":
            for c in cells:
                c["fill"] = "black" if c["rot"] in (0, 180) else "white"
            cells[3]["fill"] = "white" if cells[3]["fill"] == "black" else "black"
        elif fam == "corners":
            cells[3]["count"] = rng.choice([n for n in range(2, 6) if n != CORNERS[cells[3]["shape"]]])
        if len({_key(c) for c in cells}) < 4 or _odd_index(cells, fam) != 3:
            continue
        # 다른 기준으로 보면 다른 도형이 '다른 하나'가 되는 경우를 배제
        if any(_odd_index(cells, g) not in (None, 3) for g in ODD_FAMILIES):
            continue
        break
    else:
        raise RuntimeError(f"[{item.id}] 다른 도형 찾기 생성 실패")

    order = rng.sample(range(4), 4)
    return replace(item, choices=[_cell_svg(cells[i]) for i in order], answer=order.index(3),
                   explanation=_odd_text(fam, cells, 3), params={**item.params, "family": fam})


# ---------------------------------------------------------------- 도형 변환 기호

OPS = {
    "rot90": ("시계 90°", lambda c: {**c, "rot": (c["rot"] + 90) % 360}),
    "rot270": ("반시계 90°", lambda c: {**c, "rot": (c["rot"] + 270) % 360}),
    "rot180": ("180° 회전", lambda c: {**c, "rot": (c["rot"] + 180) % 360}),
    "invert": ("흑백 반전", lambda c: {**c, "fill": {"white": "black", "black": "white"}[c["fill"]]}),
    "add": ("1개 추가", lambda c: {**c, "count": c["count"] + 1}),
    "remove": ("1개 제거", lambda c: {**c, "count": c["count"] - 1}),
}
GLYPHS = [("◆", "#dc2626"), ("●", "#2563eb"), ("▲", "#16a34a"), ("■", "#d97706")]
TRANSFORM_LEVELS = {
    1: [["rot90", "invert"], ["add", "invert"], ["rot180", "add"], ["invert", "rot270"],
        ["remove", "rot90"], ["add", "rot90"]],
    2: [["rot90", "invert", "add"], ["rot270", "add", "invert"], ["rot180", "remove", "invert"],
        ["invert", "rot90", "remove"], ["add", "rot180", "rot90"], ["remove", "rot270", "invert"]],
    3: [["rot90", "invert", "add", "rot180"], ["rot270", "remove", "invert", "add"],
        ["invert", "rot90", "rot270", "add"], ["add", "rot180", "invert", "remove"],
        ["rot90", "add", "remove", "invert"], ["rot180", "invert", "rot90", "add"]],
    4: [["rot90", "invert", "add", "rot270"], ["rot270", "remove", "invert", "add"],
        ["invert", "rot90", "rot180", "add"], ["add", "rot180", "invert", "rot90"],
        ["rot90", "add", "remove", "invert"], ["rot180", "invert", "rot270", "add"]],
}


def _run(cell: Cell, ops: list[str]) -> Cell | None:
    for o in ops:
        cell = OPS[o][1](cell)
        if not 1 <= cell["count"] <= 5:
            return None
    return cell


def transform_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    legend: list[str] = pick_variant(spec, TRANSFORM_LEVELS[spec["level"]])
    steps = spec["level"]  # 쉬움 1단계 … 매우 어려움 4단계 (기호를 반복해서 쓸 수 있음)
    for _ in range(2000):
        start = {"shape": "arrow", "count": rng.randint(1, 4), "fill": rng.choice(["white", "black"]),
                 "rot": rng.choice([0, 90, 180, 270])}
        seq = [rng.choice(legend) for _ in range(steps)]
        if len(set(seq)) < min(steps, 3):
            continue
        ans = _run(start, seq)
        if ans is None or _key(ans) == _key(start):
            continue
        wrong = []
        for i in range(steps):  # 한 단계를 빠뜨리거나 다른 기호로 착각한 결과
            wrong.append(_run(start, seq[:i] + seq[i + 1:]))
            for other in legend:
                if other != seq[i]:
                    wrong.append(_run(start, seq[:i] + [other] + seq[i + 1:]))
        wrong += [_run(start, seq + [seq[-1]]), start]  # 한 번 더 적용하거나 아무것도 적용하지 않은 경우
        uniq = []
        for w in wrong:
            if w is not None and _key(w) != _key(ans) and _key(w) not in {_key(u) for u in uniq}:
                uniq.append(w)
        if len(uniq) >= 3:
            options = [ans, *rng.sample(uniq, 3)]
            break
    else:
        raise RuntimeError(f"[{item.id}] 도형 변환 생성 실패")

    sym = {op: GLYPHS[i] for i, op in enumerate(legend)}
    lw = 150
    body = ""
    for i, op in enumerate(legend):
        g, color = sym[op]
        body += (f'<text x="{i * lw + 8}" y="24" font-size="20" font-family="sans-serif" fill="{color}">{g}</text>'
                 f'<text x="{i * lw + 34}" y="23" font-size="16" font-family="sans-serif" fill="#111827">'
                 f'= {OPS[op][0]}</text>')
    y0 = 50
    x = 0
    body += _frame(x, y0) + _cell_body(start, x, y0)
    x += CELL
    for op in seq:
        g, color = sym[op]
        body += _arrow(x + 8, x + 70, y0 + CELL / 2)
        body += (f'<text x="{x + 36}" y="{y0 + CELL / 2 - 10}" text-anchor="middle" font-size="22" '
                 f'font-family="sans-serif" fill="{color}">{g}</text>')
        x += 78
    body += _frame(x, y0, dashed=True) + _qmark(x, y0)
    width = max(x + CELL, len(legend) * lw)
    choices, idx = _shuffle(options, rng)
    steps_text = " → ".join(f"{sym[o][0]}({OPS[o][0]})" for o in seq)
    return replace(item, stem_svg=_svg(width, y0 + CELL, body), choices=choices, answer=idx,
                   explanation=f"{steps_text} 순서로 적용한 결과는 '{_describe(ans)}'입니다.",
                   params={**item.params, "ops": seq})
