"""규칙 기반 도형 문항 생성기.

- matrix: 3×3 행렬 추론 (유동추론). 속성(모양·개수·색·방향)마다 행 단위 규칙을 적용한다.
- rotation: 폴리오미노 심적 회전 (시공간). 정답은 회전, 오답은 거울상(또는 한 칸 어긋난 모양).

문항 JSON의 svg = {"generator": ..., "seed": ...} 로 결정적으로 생성되므로
같은 문항 ID는 언제나 같은 그림·같은 정답 위치를 갖는다.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace

from core.schema import Item

INK = "#111827"
FILL_COLORS = {"white": "#ffffff", "gray": "#9ca3af", "black": INK}
SHAPES = ["circle", "square", "triangle", "pentagon", "star", "cross"]
VALUES = {"shape": SHAPES, "count": [1, 2, 3, 4, 5], "fill": list(FILL_COLORS), "rot": [0, 90, 180, 270]}

SHAPE_KO = {"circle": "원", "square": "사각형", "triangle": "삼각형", "pentagon": "오각형",
            "star": "별", "cross": "십자", "arrow": "화살표"}
FILL_KO = {"white": "흰", "gray": "회색", "black": "검은"}
DIR_KO = {0: "위", 45: "오른쪽 위", 90: "오른쪽", 135: "오른쪽 아래", 180: "아래",
          225: "왼쪽 아래", 270: "왼쪽", 315: "왼쪽 위"}
TOPIC_KO = {"shape": "모양은", "count": "개수는", "fill": "색은", "rot": "화살표 방향은"}


def materialize(item: Item) -> Item:
    from core import gen_figural, gen_numeric, gen_spatial

    generators = {
        "matrix": _matrix_item,
        "rotation": _rotation_item,
        "sequence": gen_figural.sequence_item,
        "fig_analogy": gen_figural.analogy_item,
        "odd_one_out": gen_figural.odd_one_out_item,
        "transform": gen_figural.transform_item,
        "series": gen_numeric.series_item,
        "number_matrix": gen_numeric.number_matrix_item,
        "operator": gen_numeric.operator_item,
        "data": gen_numeric.data_item,
        "paper_fold": gen_spatial.paper_fold_item,
        "cube_net": gen_spatial.cube_net_item,
        "assembly": gen_spatial.assembly_item,
    }
    gen = item.svg["generator"]
    if gen not in generators:
        raise ValueError(f"[{item.id}] 알 수 없는 생성기 {gen}")
    return generators[gen](item)


# ---------------------------------------------------------------- 공통 SVG

def _svg(w: float, h: float, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'role="img"><rect width="{w}" height="{h}" fill="#ffffff"/>{body}</svg>')


def _poly(points: list[tuple[float, float]], cx: float, cy: float, fill: str, rot: int) -> str:
    pts = " ".join(f"{cx + x:.1f},{cy + y:.1f}" for x, y in points)
    return (f'<polygon points="{pts}" fill="{fill}" stroke="{INK}" stroke-width="2" '
            f'stroke-linejoin="round" transform="rotate({rot} {cx:.1f} {cy:.1f})"/>')


def _regular(n: int, r: float, inner: float | None = None) -> list[tuple[float, float]]:
    pts = []
    steps = n * 2 if inner else n
    for i in range(steps):
        rr = r if not inner or i % 2 == 0 else r * inner
        a = -math.pi / 2 + 2 * math.pi * i / steps
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    return pts


def _shape(shape: str, cx: float, cy: float, r: float, fill: str, rot: int) -> str:
    if shape == "circle":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * 0.9:.1f}" fill="{fill}" stroke="{INK}" stroke-width="2"/>'
    if shape == "square":
        s = r * 0.8
        return _poly([(-s, -s), (s, -s), (s, s), (-s, s)], cx, cy, fill, rot)
    if shape == "triangle":
        return _poly(_regular(3, r), cx, cy + r * 0.15, fill, rot)
    if shape == "pentagon":
        return _poly(_regular(5, r), cx, cy, fill, rot)
    if shape == "star":
        return _poly(_regular(5, r, inner=0.45), cx, cy, fill, rot)
    if shape == "cross":
        w = r * 0.34
        return _poly([(-w, -r), (w, -r), (w, -w), (r, -w), (r, w), (w, w), (w, r), (-w, r),
                       (-w, w), (-r, w), (-r, -w), (-w, -w)], cx, cy, fill, rot)
    if shape == "arrow":
        return _poly([(0, -r), (0.75 * r, -0.05 * r), (0.28 * r, -0.05 * r), (0.28 * r, r),
                      (-0.28 * r, r), (-0.28 * r, -0.05 * r), (-0.75 * r, -0.05 * r)], cx, cy, fill, rot)
    raise ValueError(shape)


# ---------------------------------------------------------------- 행렬 추론

CELL = 100
GAP = 8
POSITIONS = {
    1: [(50, 50)],
    2: [(28, 50), (72, 50)],
    3: [(50, 27), (27, 72), (73, 72)],
    4: [(29, 29), (71, 29), (29, 71), (71, 71)],
    5: [(25, 25), (75, 25), (50, 50), (25, 75), (75, 75)],
}
RADIUS = {1: 30, 2: 18, 3: 17, 4: 16, 5: 13}


def _cell_body(cell: dict, x: float, y: float) -> str:
    n = cell["count"]
    return "".join(
        _shape(cell["shape"], x + px, y + py, RADIUS[n], FILL_COLORS[cell["fill"]], cell["rot"])
        for px, py in POSITIONS[n]
    )


def _frame(x: float, y: float, dashed: bool = False) -> str:
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    return (f'<rect x="{x + 1}" y="{y + 1}" width="{CELL - 2}" height="{CELL - 2}" rx="6" '
            f'fill="none" stroke="#6b7280" stroke-width="1.5"{dash}/>')


def _matrix_svg(grid: list[list[dict]]) -> str:
    size = 3 * CELL + 2 * GAP
    body = ""
    for r in range(3):
        for c in range(3):
            x, y = c * (CELL + GAP), r * (CELL + GAP)
            if (r, c) == (2, 2):
                body += _frame(x, y, dashed=True)
                body += (f'<text x="{x + 50}" y="{y + 64}" text-anchor="middle" font-size="44" '
                         f'font-family="sans-serif" font-weight="700" fill="#6b7280">?</text>')
            else:
                body += _frame(x, y) + _cell_body(grid[r][c], x, y)
    return _svg(size, size, body)


def _cell_svg(cell: dict) -> str:
    return _svg(CELL, CELL, _frame(0, 0) + _cell_body(cell, 0, 0))


def _rule_grid(attr: str, rule: str, rng: random.Random) -> list[list]:
    vals = VALUES[attr]
    if rule == "const":
        picks = rng.sample(vals, 3)
        return [[picks[r]] * 3 for r in range(3)]
    if rule == "dist":
        picks = rng.sample(vals, 3)
        shifts = rng.sample(range(3), 3)  # 라틴 방진: 행·열 모두 세 값이 한 번씩
        return [[picks[(c + shifts[r]) % 3] for c in range(3)] for r in range(3)]
    if rule == "prog" and attr == "count":
        return [[s + c for c in range(3)] for s in rng.sample([1, 2, 3], 3)]
    if rule == "prog" and attr == "rot":
        step = rng.choice([1, -1])
        return [[vals[(s + c * step) % 4] for c in range(3)] for s in rng.sample(range(4), 3)]
    raise ValueError(f"지원하지 않는 규칙 {attr}:{rule}")


def _rule_text(attr: str, rule: str, grid: list[list]) -> str:
    topic = TOPIC_KO[attr]
    if rule == "const":
        return f"{topic} 한 행 안에서 모두 같고 행마다 다릅니다."
    if rule == "dist":
        return f"{topic} 각 행에 세 가지가 한 번씩 나옵니다."
    if attr == "count":
        return "개수는 오른쪽으로 갈수록 1개씩 늘어납니다."
    clockwise = (grid[0][1] - grid[0][0]) % 360 == 90
    return f"화살표는 오른쪽으로 갈수록 {'시계' if clockwise else '반시계'} 방향으로 90°씩 돕니다."


def _describe(cell: dict) -> str:
    text = f"{FILL_KO[cell['fill']]} {SHAPE_KO[cell['shape']]} {cell['count']}개"
    if cell["shape"] == "arrow":
        text += f"({DIR_KO[cell['rot']]} 방향)"
    return text


# 난이도별 규칙 조합 후보. 동형 문항마다 다른 조합을 써서 겉모습·풀이가 겹치지 않게 한다.
MATRIX_LEVELS: dict[int, list[dict[str, str]]] = {
    1: [{"count": "prog"}, {"shape": "dist"}, {"rot": "prog"}, {"fill": "dist"},
        {"count": "dist"}, {"shape": "const"}],
    2: [{"shape": "dist", "fill": "const"}, {"count": "prog", "fill": "dist"},
        {"shape": "const", "count": "dist"}, {"rot": "prog", "fill": "dist"},
        {"shape": "dist", "count": "prog"}, {"rot": "prog", "count": "dist"}],
    3: [{"shape": "dist", "count": "prog", "fill": "dist"}, {"rot": "prog", "count": "dist", "fill": "dist"},
        {"shape": "dist", "count": "dist", "fill": "dist"}, {"rot": "prog", "count": "prog", "fill": "dist"},
        {"shape": "const", "count": "dist", "fill": "dist"}, {"shape": "dist", "count": "prog", "fill": "const"}],
}


def pick_variant(spec: dict, options: list):
    """동형 문항 번호(form)마다 서로 다른 후보를 고른다. 슬롯마다 순서는 다르게 섞는다."""
    if "form" not in spec:
        return random.Random(spec["seed"]).choice(options)
    order = random.Random(spec["pool_seed"]).sample(range(len(options)), len(options))
    return options[order[spec["form"] % len(options)]]


def _matrix_item(item: Item) -> Item:
    spec = item.svg
    rules: dict[str, str] = spec.get("rules") or pick_variant(spec, MATRIX_LEVELS[spec["level"]])
    rng = random.Random(spec["seed"])
    if "rot" in rules and "shape" in rules:
        raise ValueError(f"[{item.id}] 방향 규칙은 모양이 고정(화살표)일 때만 쓸 수 있음")
    if not 1 <= len(rules) <= 3:
        raise ValueError(f"[{item.id}] 규칙은 1~3개")

    fixed = {
        "shape": "arrow" if "rot" in rules else rng.choice(SHAPES),
        "count": rng.choice([1, 2, 3]),
        "fill": rng.choice(VALUES["fill"]),
        "rot": 0,
    }
    grids = {a: _rule_grid(a, rule, rng) for a, rule in rules.items()}
    cells = [[{a: (grids[a][r][c] if a in grids else fixed[a]) for a in fixed} for c in range(3)]
             for r in range(3)]
    answer = cells[2][2]

    def alternative(attr: str):
        if attr in rules:
            g = grids[attr]
            cands = {"const": [g[0][2], g[1][2]], "dist": [g[2][0], g[2][1]]}.get(rules[attr])
            if cands is None:  # prog: 바로 앞 칸 값 또는 한 단계 더 간 값
                if attr == "count":
                    cands = [g[2][1]] + ([g[2][2] + 1] if g[2][2] < 5 else [])
                else:
                    cands = [g[2][1], (g[2][2] + 180) % 360]
        else:
            cands = [v for v in VALUES[attr] if v != fixed[attr]]
        cands = [v for v in cands if v != answer[attr]]
        return rng.choice(cands)

    if len(rules) == 1:
        partner = next(a for a in ("fill", "count", "shape") if a not in rules and not
                       (a == "shape" and fixed["shape"] == "arrow"))
        attrs = [*rules, partner]
    else:
        attrs = list(rules)
    # 균형 설계: 각 속성의 정답 값이 보기 4개 중 정확히 2개에 나와 빈도로 정답을 짐작할 수 없게 한다
    patterns = [(0, 0), (1, 0), (0, 1), (1, 1)] if len(attrs) == 2 else \
        [(0, 0, 0), (1, 1, 0), (1, 0, 1), (0, 1, 1)]
    alts = {a: alternative(a) for a in attrs}
    options = []
    for pat in patterns:
        cell = dict(answer)
        for a, flip in zip(attrs, pat):
            if flip:
                cell[a] = alts[a]
        options.append(cell)

    keys = [tuple(sorted(o.items())) for o in options]
    assert len(set(keys)) == 4 and keys.count(tuple(sorted(answer.items()))) == 1, item.id

    order = rng.sample(range(4), 4)
    choices = [_cell_svg(options[i]) for i in order]
    explanation = item.explanation or (
        " ".join(_rule_text(a, rules[a], grids[a]) for a in rules)
        + f" 따라서 정답은 '{_describe(answer)}'입니다."
    )
    return replace(item, stem_svg=_matrix_svg(cells), choices=choices, answer=order.index(0),
                   explanation=explanation, params={**item.params, "rules": rules})


# ---------------------------------------------------------------- 심적 회전

Cells = frozenset[tuple[int, int]]
NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _norm(cells) -> Cells:
    cells = list(cells)
    mx = min(x for x, _ in cells)
    my = min(y for _, y in cells)
    return frozenset((x - mx, y - my) for x, y in cells)


def _rot90(cells: Cells) -> Cells:  # 화면 좌표(y 아래)에서 시계 방향 90°
    return _norm((-y, x) for x, y in cells)


def _rotate(cells: Cells, k: int) -> Cells:
    for _ in range(k % 4):
        cells = _rot90(cells)
    return cells


def _mirror(cells: Cells) -> Cells:
    return _norm((-x, y) for x, y in cells)


def _connected(cells: Cells) -> bool:
    start = next(iter(cells))
    seen, stack = {start}, [start]
    while stack:
        x, y = stack.pop()
        for dx, dy in NEIGHBORS:
            n = (x + dx, y + dy)
            if n in cells and n not in seen:
                seen.add(n)
                stack.append(n)
    return len(seen) == len(cells)


def _random_polyomino(n: int, rng: random.Random) -> Cells:
    """회전 대칭이 없고 거울상과 구별되는(키랄) 폴리오미노."""
    while True:
        cells = {(0, 0)}
        while len(cells) < n:
            x, y = rng.choice(sorted(cells))
            dx, dy = rng.choice(NEIGHBORS)
            cells.add((x + dx, y + dy))
        shape = _norm(cells)
        rots = {_rotate(shape, k) for k in range(4)}
        if len(rots) == 4 and _mirror(shape) not in rots:
            return shape


def _near_miss(shape: Cells, forbidden: set[Cells], rng: random.Random) -> Cells:
    """칸 하나를 다른 자리로 옮긴, 연결된 비슷한 모양."""
    cells = sorted(shape)
    for _ in range(500):
        removed = rng.choice(cells)
        rest = frozenset(c for c in cells if c != removed)
        x, y = rng.choice(sorted(rest))
        dx, dy = rng.choice(NEIGHBORS)
        added = (x + dx, y + dy)
        if added in rest or added == removed:
            continue
        cand = _norm(rest | {added})
        if _connected(cand) and cand not in forbidden:
            return cand
    raise RuntimeError("near-miss 생성 실패")


def _poly_svg(cells: Cells, size: int = 120) -> str:
    w = max(x for x, _ in cells) + 1
    h = max(y for _, y in cells) + 1
    unit = min(22, (size - 16) / max(w, h))
    ox, oy = (size - w * unit) / 2, (size - h * unit) / 2
    body = "".join(
        f'<rect x="{ox + x * unit:.1f}" y="{oy + y * unit:.1f}" width="{unit:.1f}" height="{unit:.1f}" '
        f'fill="#4F46E5" stroke="#ffffff" stroke-width="2"/>'
        for x, y in sorted(cells)
    )
    return _svg(size, size, body)


def _rotation_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    shape = _random_polyomino(spec["cells"], rng)
    k = rng.choice([1, 2, 3])
    correct = _rotate(shape, k)
    mirrors = [_rotate(_mirror(shape), j) for j in rng.sample(range(4), 3)]
    near = spec.get("near_miss", False)
    if near:
        forbidden = {_rotate(shape, j) for j in range(4)} | {_rotate(_mirror(shape), j) for j in range(4)}
        options = [correct, mirrors[0], mirrors[1], _near_miss(correct, forbidden, rng)]
    else:
        options = [correct, *mirrors]
    assert len(set(options)) == 4, item.id

    order = rng.sample(range(4), 4)
    explanation = item.explanation or (
        f"정답은 위 도형을 시계 방향으로 {90 * k}° 돌린 모양입니다. 나머지는 도형을 뒤집은(거울상) 모양"
        + ("이거나 칸 하나의 위치가 다른 모양" if near else "")
        + "이라 돌리기만으로는 만들 수 없습니다."
    )
    return replace(item, stem_svg=_poly_svg(shape), choices=[_poly_svg(options[i]) for i in order],
                   answer=order.index(0), explanation=explanation)
