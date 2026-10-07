"""시공간 생성기: 종이 접어 구멍 뚫기, 정육면체 전개도, 조각 맞추기.

정답은 모두 시뮬레이션으로 계산한다 (펼친 구멍 위치, 접은 면의 법선, 조각 회전 비교).
"""

from __future__ import annotations

import random
from dataclasses import replace

from core.figures import (INK, NEIGHBORS, Cells, _connected, _mirror, _near_miss, _norm, _poly_svg, _rotate,
                          _shape, _svg, pick_variant)
from core.schema import Item

# ---------------------------------------------------------------- 종이 접어 구멍 뚫기

N = 4          # 종이는 4×4 칸
U = 22         # 칸 크기(px)
PAPER = N * U
FOLDS = {      # 접는 방향: (접혀 넘어가는 쪽, 남는 쪽, 대칭축)
    "L": ("왼쪽을 오른쪽으로", "v"), "R": ("오른쪽을 왼쪽으로", "v"),
    "T": ("위쪽을 아래쪽으로", "h"), "B": ("아래쪽을 위쪽으로", "h"),
}
FOLD_LEVELS = {1: [["L"], ["T"], ["R"], ["B"], ["L"], ["T"]],
               2: [["L", "T"], ["T", "R"], ["R", "B"], ["B", "L"], ["L", "B"], ["T", "L"]]}


def _visible(folds: list[str]) -> tuple[range, range]:
    cols, rows = range(N), range(N)
    for f in folds:
        if f == "L":
            cols = range(cols.start + len(cols) // 2, cols.stop)
        elif f == "R":
            cols = range(cols.start, cols.stop - len(cols) // 2)
        elif f == "T":
            rows = range(rows.start + len(rows) // 2, rows.stop)
        else:
            rows = range(rows.start, rows.stop - len(rows) // 2)
    return cols, rows


def _unfold(holes: set, folds: list[str], axes: list[str] | None = None) -> frozenset:
    """접은 순서의 역순으로 펼치며 대칭 구멍을 추가한다. axes로 축을 바꿔 오답을 만든다."""
    holes = set(holes)
    for i, f in enumerate(reversed(folds)):
        axis = (axes or [FOLDS[x][1] for x in reversed(folds)])[i]
        holes |= {(N - 1 - c, r) if axis == "v" else (c, N - 1 - r) for c, r in holes}
    return frozenset(holes)


def _paper(x: float, y: float, cols: range, rows: range, holes=(), fold: str | None = None) -> str:
    out = (f'<rect x="{x}" y="{y}" width="{PAPER}" height="{PAPER}" fill="none" stroke="#d1d5db" '
           f'stroke-dasharray="3 4"/>'
           f'<rect x="{x + cols.start * U}" y="{y + rows.start * U}" width="{len(cols) * U}" '
           f'height="{len(rows) * U}" fill="#fef9c3" stroke="{INK}" stroke-width="1.5"/>')
    for c, r in holes:
        out += f'<circle cx="{x + (c + .5) * U}" cy="{y + (r + .5) * U}" r="{U * .28}" fill="{INK}"/>'
    if fold:
        cx = x + (cols.start + len(cols) / 2) * U
        cy = y + (rows.start + len(rows) / 2) * U
        if FOLDS[fold][1] == "v":
            out += (f'<line x1="{cx}" y1="{y + rows.start * U}" x2="{cx}" y2="{y + rows.stop * U}" '
                    f'stroke="#dc2626" stroke-width="2" stroke-dasharray="5 4"/>')
            sx, ex = (cx - len(cols) * U / 4, cx + len(cols) * U / 4) if fold == "L" else \
                (cx + len(cols) * U / 4, cx - len(cols) * U / 4)
            out += _curve(sx, cy, ex, cy)
        else:
            out += (f'<line x1="{x + cols.start * U}" y1="{cy}" x2="{x + cols.stop * U}" y2="{cy}" '
                    f'stroke="#dc2626" stroke-width="2" stroke-dasharray="5 4"/>')
            sy, ey = (cy - len(rows) * U / 4, cy + len(rows) * U / 4) if fold == "T" else \
                (cy + len(rows) * U / 4, cy - len(rows) * U / 4)
            out += _curve(cx, sy, cx, ey)
    return out


def _curve(x1: float, y1: float, x2: float, y2: float) -> str:
    mx, my = (x1 + x2) / 2 - (y2 - y1) * .4, (y1 + y2) / 2 - (x2 - x1) * .4
    return (f'<path d="M{x1},{y1} Q{mx},{my} {x2},{y2}" fill="none" stroke="#dc2626" stroke-width="2"/>'
            f'<circle cx="{x2}" cy="{y2}" r="3.5" fill="#dc2626"/>')


def _sheet_svg(holes: frozenset) -> str:
    body = "".join(f'<line x1="{i * U + 4}" y1="4" x2="{i * U + 4}" y2="{PAPER + 4}" stroke="#f3f4f6"/>'
                   f'<line x1="4" y1="{i * U + 4}" x2="{PAPER + 4}" y2="{i * U + 4}" stroke="#f3f4f6"/>'
                   for i in range(1, N))
    body += f'<rect x="4" y="4" width="{PAPER}" height="{PAPER}" fill="none" stroke="{INK}" stroke-width="1.5"/>'
    body += "".join(f'<circle cx="{4 + (c + .5) * U}" cy="{4 + (r + .5) * U}" r="{U * .28}" fill="{INK}"/>'
                    for c, r in sorted(holes))
    return _svg(PAPER + 8, PAPER + 8, body)


def paper_fold_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    folds: list[str] = pick_variant(spec, FOLD_LEVELS[spec["level"]])
    cols, rows = _visible(folds)
    region = [(c, r) for c in cols for r in rows]
    punches = set(rng.sample(region, 2 if len(folds) == 1 and rng.random() < .5 else 1))
    ans = _unfold(punches, folds)

    other = {"v": "h", "h": "v"}
    wrong = [frozenset(punches), _unfold(punches, folds, [other[FOLDS[f][1]] for f in reversed(folds)])]
    if len(folds) == 2:
        wrong += [_unfold(punches, folds[:1]), _unfold(punches, folds[1:])]
    else:
        wrong += [_unfold(punches, folds + ["T" if FOLDS[folds[0]][1] == "v" else "L"])]
    for dc, dr in ((1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)):  # 구멍 위치를 한 칸 잘못 본 경우
        wrong.append(_unfold({((c + dc) % N, (r + dr) % N) for c, r in punches}, folds))
    wrong.append(frozenset(ans - punches))  # 뚫은 구멍을 빠뜨린 경우
    uniq = []
    for w in wrong:
        if w != ans and w not in uniq:
            uniq.append(w)
    options = [ans, *uniq[:3]]
    assert len(set(options)) == 4, item.id

    panels, x, gap = [], 0, 46
    state: list[str] = []
    for f in folds:
        panels.append(_paper(x, 0, *_visible(state), fold=f))
        state.append(f)
        x += PAPER + gap
    panels.append(_paper(x, 0, *_visible(state), holes=punches))
    arrows = "".join(
        f'<polygon points="{(i + 1) * (PAPER + gap) - 14},{PAPER / 2} {(i + 1) * (PAPER + gap) - 26},'
        f'{PAPER / 2 - 7} {(i + 1) * (PAPER + gap) - 26},{PAPER / 2 + 7}" fill="#6b7280"/>'
        for i in range(len(folds)))
    order = rng.sample(range(4), 4)
    how = ", ".join(FOLDS[f][0] for f in folds)
    return replace(item, stem_svg=_svg(x + PAPER, PAPER, "".join(panels) + arrows),
                   choices=[_sheet_svg(options[i]) for i in order], answer=order.index(0),
                   explanation=f"종이를 {how} 접은 뒤 구멍을 뚫었습니다. 접은 선을 기준으로 대칭이 되도록 "
                               f"거꾸로 펼치면 구멍은 {len(ans)}개가 됩니다.",
                   params={**item.params, "folds": folds})


# ---------------------------------------------------------------- 정육면체 전개도

FACE_SYMBOLS = ["circle", "square", "triangle", "star", "cross", "pentagon"]
FACE_KO = {"circle": "●", "square": "■", "triangle": "▲", "star": "★", "cross": "✚", "pentagon": "⬟"}


def _neg(v):
    return tuple(-a for a in v)


def fold_cube(cells: Cells) -> dict | None:
    """전개도 칸 → 접었을 때 바깥 법선. 정육면체가 안 되면 None."""
    start = min(cells)
    frames = {start: ((0, 0, 1), (1, 0, 0), (0, 1, 0))}  # (normal, right, down)
    stack = [start]
    while stack:
        cur = stack.pop()
        n, r, d = frames[cur]
        moves = {(1, 0): (r, _neg(n), d), (-1, 0): (_neg(r), n, d),
                 (0, 1): (d, r, _neg(n)), (0, -1): (_neg(d), r, n)}
        for (dx, dy), frame in moves.items():
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in cells and nxt not in frames:
                frames[nxt] = frame
                stack.append(nxt)
    normals = {c: f[0] for c, f in frames.items()}
    return normals if len(set(normals.values())) == 6 else None


def _random_net(rng: random.Random, long_row: bool) -> Cells:
    while True:
        cells = {(0, 0)}
        while len(cells) < 6:
            x, y = rng.choice(sorted(cells))
            dx, dy = rng.choice(NEIGHBORS)
            cells.add((x + dx, y + dy))
        net = _norm(cells)
        if fold_cube(net) is None:
            continue
        rows = [sum(1 for c in net if c[1] == y) for y in range(4)]
        cols = [sum(1 for c in net if c[0] == x) for x in range(4)]
        if (max(rows + cols) >= 4) == long_row:  # 보통: 1-4-1형, 어려움: 그 밖의 전개도
            return net


def _glyph(sym: str, cx: float, cy: float, r: float) -> str:
    return _shape(sym, cx, cy, r, INK, 0)


def cube_net_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    net = _random_net(rng, long_row=spec["level"] == 2)
    normals = fold_cube(net)
    cells = sorted(net)
    syms = dict(zip(cells, rng.sample(FACE_SYMBOLS, 6)))
    ask = rng.choice(cells)
    opposite = next(c for c in cells if normals[c] == _neg(normals[ask]))
    adjacent = [c for c in cells if c not in (ask, opposite)]
    options = [syms[opposite], *[syms[c] for c in rng.sample(adjacent, 3)]]

    u = 56
    w, h = (max(x for x, _ in cells) + 1) * u, (max(y for _, y in cells) + 1) * u
    body = ""
    for c in cells:
        x, y = c[0] * u, c[1] * u
        fill = "#fef9c3" if c == ask else "#ffffff"
        body += (f'<rect x="{x + 1}" y="{y + 1}" width="{u - 2}" height="{u - 2}" fill="{fill}" '
                 f'stroke="{INK}" stroke-width="1.5"/>' + _glyph(syms[c], x + u / 2, y + u / 2, u * .28))
    order = rng.sample(range(4), 4)
    glyph_svg = [_svg(60, 60, _glyph(options[i], 30, 30, 20)) for i in order]
    return replace(item, stem_svg=_svg(w, h, body), choices=glyph_svg, answer=order.index(0),
                   prompt=f"전개도를 접어 정육면체를 만들 때, {FACE_KO[syms[ask]]} 면(노란 칸)과 마주 보는 면은?",
                   explanation=f"접으면 {FACE_KO[syms[ask]]} 면의 맞은편에는 {FACE_KO[syms[opposite]]} 면이 옵니다. "
                               f"나머지 보기는 {FACE_KO[syms[ask]]} 면과 모서리를 맞대는 옆면입니다.",
                   params={**item.params, "net": cells})


# ---------------------------------------------------------------- 조각 맞추기

def _split_square(n: int, rng: random.Random) -> tuple[Cells, Cells]:
    square = {(x, y) for x in range(n) for y in range(n)}
    while True:
        size = rng.randint(n * n // 2 - 1, n * n // 2 + 1)
        a = {rng.choice(sorted(square))}
        while len(a) < size:
            x, y = rng.choice(sorted(a))
            dx, dy = rng.choice(NEIGHBORS)
            if (x + dx, y + dy) in square:
                a.add((x + dx, y + dy))
        b = frozenset(square - a)
        rots_b = {_rotate(_norm(b), k) for k in range(4)}
        if _connected(b) and len(rots_b) == 4 and _mirror(_norm(b)) not in rots_b:
            return frozenset(a), b


def _fits(piece: Cells, b: Cells) -> bool:
    return any(_rotate(piece, k) == _norm(b) for k in range(4))


def assembly_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    n = spec["size"]
    a, b = _split_square(n, rng)
    nb = _norm(b)
    correct = _rotate(nb, rng.choice([1, 2, 3]))
    forbidden = {_rotate(nb, k) for k in range(4)}
    wrong = [_rotate(_mirror(nb), rng.randrange(4))]
    while len(wrong) < 3:
        cand = _near_miss(nb, forbidden | {_rotate(w, k) for w in wrong for k in range(4)}, rng)
        wrong.append(_rotate(cand, rng.randrange(4)))
    options = [correct, *wrong]
    assert _fits(correct, b) and not any(_fits(w, b) for w in wrong), item.id

    u = 22
    side = n * u + 16
    body = f'<rect x="8" y="8" width="{n * u}" height="{n * u}" fill="none" stroke="#9ca3af" stroke-dasharray="4 4"/>'
    body += "".join(f'<rect x="{8 + x * u}" y="{8 + y * u}" width="{u}" height="{u}" fill="#9ca3af" '
                    f'stroke="#ffffff" stroke-width="2"/>' for x, y in sorted(a))
    order = rng.sample(range(4), 4)
    return replace(item, stem_svg=_svg(side, side, body), choices=[_poly_svg(options[i]) for i in order],
                   answer=order.index(0),
                   explanation=f"회색 조각의 빈 칸({len(b)}칸)을 정확히 채우는 조각을 돌려 놓은 것이 정답입니다. "
                               "나머지는 뒤집은 모양이거나 칸 하나의 위치가 달라 빈틈이 생깁니다.",
                   params={**item.params, "size": n})
