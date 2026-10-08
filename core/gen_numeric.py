"""수리 영역 생성기: 수열, 수 행렬, 연산 기호 추론, 자료 해석.

모든 생성기는 정답을 코드로 계산하고, 오답은 흔한 풀이 실수에서 나온 값으로 만든다.
"""

from __future__ import annotations

import random
from fractions import Fraction
from dataclasses import replace

from core.figures import _svg, pick_variant
from core.schema import Item


def josa(n: int, pair: str) -> str:
    """숫자 뒤 조사: 읽었을 때 받침이 있으면 앞 글자(을/이), 없으면 뒤 글자(를/가)."""
    has_batchim = abs(n) % 10 in (0, 1, 3, 6, 7, 8)
    first, second = pair.split("/")
    return f"{n:,}{first if has_batchim else second}"


def _options(answer, wrong: list, rng: random.Random, spread: int = 3) -> tuple[list[str], int]:
    """정답 + 그럴듯한 오답 3개를 섞어 (보기, 정답 인덱스)를 돌려준다."""
    picks: list = []
    for w in wrong:
        if w != answer and w not in picks and (not isinstance(w, (int, float)) or w > 0):
            picks.append(w)
    step = 1
    while len(picks) < 3:  # 오답 후보가 모자라면 정답 근처 값으로 채운다
        for w in (answer + step * spread, answer - step * spread, answer + step):
            if len(picks) < 3 and w > 0 and w != answer and w not in picks:
                picks.append(w)
        step += 1
    values = [answer, *rng.sample(picks[:3], 3)]
    order = rng.sample(range(4), 4)
    return [f"{values[i]:,}" if isinstance(values[i], int) else str(values[i]) for i in order], order.index(0)


# ---------------------------------------------------------------- 수열

def _series(kind: str, rng: random.Random) -> tuple[list[int], int, list[int], str]:
    """(제시 항, 정답, 오답 후보, 해설)"""
    if kind == "arith":
        a, d = rng.randint(2, 15), rng.randint(3, 9)
        s = [a + d * i for i in range(6)]
        return s[:5], s[5], [s[5] + 1, s[5] - 1, s[4] + d + d], f"{d}씩 커지는 수열입니다."
    if kind == "arith_down":
        a, d = rng.randint(60, 99), rng.randint(4, 9)
        s = [a - d * i for i in range(6)]
        return s[:5], s[5], [s[5] + 1, s[5] - 1, s[5] - d], f"{d}씩 작아지는 수열입니다."
    if kind == "geom":
        a, r = rng.randint(1, 4), rng.choice([2, 3])
        s = [a * r ** i for i in range(6)]
        return s[:5], s[5], [s[4] + (s[4] - s[3]), s[5] - s[4] // 2, s[4] * (r + 1)], f"앞의 수에 {josa(r, '을/를')} 곱하는 수열입니다."
    if kind == "second_order":
        a, d, k = rng.randint(1, 10), rng.randint(1, 4), rng.randint(2, 3)
        s = [a]
        for i in range(5):
            s.append(s[-1] + d + k * i)
        last_diff = s[4] - s[3]
        return s[:5], s[5], [s[4] + last_diff, s[5] + k, s[5] - 1], \
            f"이웃한 두 수의 차이가 {d}부터 {k}씩 커집니다. 다음 차이는 {d + 4 * k}입니다."
    if kind == "interleaved":
        a, b, d, e = rng.randint(1, 9), rng.randint(20, 40), rng.randint(2, 5), rng.randint(2, 5)
        s = [a + d * (i // 2) if i % 2 == 0 else b - e * (i // 2) for i in range(7)]
        return s[:6], s[6], [s[5] - e, s[6] + d, s[4] + d + 1], \
            f"홀수 번째는 {d}씩 커지고, 짝수 번째는 {e}씩 작아지는 두 수열이 번갈아 나옵니다."
    if kind == "squares":
        c, off = rng.choice([-1, 1, 2, 3]), rng.randint(1, 3)
        s = [(i + off) ** 2 + c for i in range(6)]
        sign = f"+ {c}" if c > 0 else f"− {-c}"
        return s[:5], s[5], [s[5] - 1, s[5] + 2, s[4] + (s[4] - s[3])], f"연속한 자연수의 제곱 {sign} 꼴입니다."
    if kind == "fib":
        a, b = rng.randint(1, 4), rng.randint(2, 6)
        s = [a, b]
        while len(s) < 7:
            s.append(s[-1] + s[-2])
        return s[:6], s[6], [s[5] + (s[5] - s[4]), s[6] + 1, s[5] * 2], "앞의 두 수를 더하면 다음 수가 됩니다."
    if kind == "double_diff":
        a, d = rng.randint(1, 10), rng.choice([1, 2, 3])
        s = [a]
        for i in range(5):
            s.append(s[-1] + d * 2 ** i)
        return s[:5], s[5], [s[4] + d * 2 ** 3, s[5] + d, s[5] - d], \
            f"차이가 {d}, {2 * d}, {4 * d}, …로 두 배씩 커집니다."
    if kind == "mult_add":
        a, m, c = rng.randint(1, 4), 2, rng.choice([1, -1, 2])
        s = [a]
        for _ in range(5):
            s.append(s[-1] * m + c)
        sign = f"{josa(c, '을/를')} 더하는" if c > 0 else f"{josa(-c, '을/를')} 빼는"
        return s[:5], s[5], [s[4] * m, s[5] + 2 * c, s[4] * m - c * 3], f"앞의 수에 {josa(m, '을/를')} 곱하고 {sign} 규칙입니다."
    # ---- 어려움
    if kind in ("alt_ops", "alt_ops3x"):
        a, p, m = rng.randint(2, 6), rng.randint(2, 5), 2 if kind == "alt_ops" else 3
        s = [a]
        for i in range(6):
            s.append(s[-1] + p if i % 2 == 0 else s[-1] * m)
        return s[:6], s[6], [s[5] + p, s[5] * m + p, s[6] + m], f"+{p}와 ×{m}를 번갈아 적용합니다."
    if kind == "products":
        m = rng.randint(1, 3)
        s = [n * (n + 1) for n in range(m, m + 6)]
        return s[:5], s[5], [s[4] + (s[4] - s[3]), s[5] + 2, (m + 5) ** 2], "연속한 두 자연수의 곱(n × (n+1))입니다."
    if kind == "fib3":
        s = [rng.randint(1, 3) for _ in range(3)]
        while len(s) < 7:
            s.append(s[-1] + s[-2] + s[-3])
        return s[:6], s[6], [s[5] + s[4], s[6] + 1, s[5] * 2], "앞의 세 수를 더하면 다음 수가 됩니다."
    if kind == "geom_diff":
        a, d = rng.randint(1, 9), rng.randint(1, 2)
        s = [a]
        for i in range(5):
            s.append(s[-1] + d * 3 ** i)
        return s[:5], s[5], [s[4] + (s[4] - s[3]), s[4] + 2 * (s[4] - s[3]), s[5] + d],             f"차이가 {d}, {3 * d}, {9 * d}, …로 3배씩 커집니다."
    if kind == "cubes":
        c = rng.choice([-1, 1, 2])
        s = [n ** 3 + c for n in range(1, 7)]
        sign = f"+ {c}" if c > 0 else f"− {-c}"
        return s[:5], s[5], [s[4] + (s[4] - s[3]), 36 + c, s[5] + 1], f"연속한 자연수의 세제곱 {sign} 꼴입니다."
    # ---- 매우 어려움
    if kind == "interleaved_mult":
        a, b, d = rng.randint(1, 3), rng.randint(10, 30), rng.randint(2, 5)
        s = [a * 2 ** (i // 2) if i % 2 == 0 else b + d * (i // 2) for i in range(9)]
        return s[:8], s[8], [b + d * 4, s[6] + a * 4, s[8] + a],             f"홀수 번째는 2배씩, 짝수 번째는 {d}씩 커지는 두 수열이 번갈아 나옵니다."
    if kind == "alt_ops3":
        while True:
            a, p, q = rng.randint(2, 6), rng.randint(2, 5), rng.randint(1, 4)
            s = [a]
            for i in range(7):
                s.append([s[-1] + p, s[-1] * 2, s[-1] - q][i % 3])
            if min(s) > 0:
                break
        return s[:7], s[7], [s[6] * 2, s[6] - q, s[7] + 1], f"+{p}, ×2, −{q}를 차례로 반복합니다."
    if kind == "diff_fib":
        a = rng.randint(1, 10)
        s = [a]
        for d in (1, 1, 2, 3, 5, 8):
            s.append(s[-1] + d)
        return s[:6], s[6], [s[5] + 5, s[5] + 7, s[6] + 1], "차이가 1, 1, 2, 3, 5, …로 앞의 두 차이를 더한 값(피보나치)입니다."
    if kind == "mult_add_var":
        s = [rng.randint(1, 3)]
        for i in range(1, 6):
            s.append(s[-1] * 2 + i)
        return s[:5], s[5], [s[4] * 2, s[4] * 2 + 4, s[5] + 1], "앞의 수에 2를 곱하고 1, 2, 3, …을 차례로 더합니다."
    if kind == "diff_squares":
        a = rng.randint(1, 9)
        s = [a]
        for n in range(2, 7):
            s.append(s[-1] + n * n)
        return s[:5], s[5], [s[4] + 25, s[4] + 49, s[5] + 1], "차이가 4, 9, 16, 25, …로 연속한 제곱수입니다."
    if kind == "factorial_like":
        a = rng.randint(1, 3)
        s = [a]
        for i in range(1, 6):
            s.append(s[-1] * i)
        return s[:5], s[5], [s[4] * 4, s[4] * 6, s[4] + 24 * a], "앞의 수에 1, 2, 3, 4, …를 차례로 곱합니다."
    raise ValueError(kind)


SERIES_LEVELS = {
    1: ["arith", "arith_down", "geom", "arith", "geom", "arith_down"],
    2: ["second_order", "interleaved", "squares", "fib", "double_diff", "mult_add"],
    3: ["alt_ops", "products", "fib3", "geom_diff", "cubes", "alt_ops3x"],
    4: ["interleaved_mult", "alt_ops3", "diff_fib", "mult_add_var", "diff_squares", "factorial_like"],
}


def _poly_next(seq: list[Fraction], max_deg: int = 3) -> Fraction | None:
    """k차 차분이 일정하면(k차 다항식) 다음 항. 확인용 값이 최소 2개 남는 차수까지만 본다."""
    rows = [list(seq)]
    for _ in range(max_deg):
        rows.append([b - a for a, b in zip(rows[-1], rows[-1][1:])])
        if len(rows[-1]) >= 2 and len(set(rows[-1])) == 1:
            nxt = rows[-1][-1]
            for r in reversed(rows[:-1]):
                nxt = r[-1] + nxt
            return nxt
    return None


def _linear_rec_next(seq: list[Fraction]) -> set[Fraction]:
    """앞 항으로 만드는 점화식들: a(n+1) = p·a(n) + q, a(n+2) = p·a(n+1) + q·a(n) (+ r)."""
    out = set()
    n = len(seq)
    if n >= 4 and seq[1] != seq[0]:  # 1차: 미지수 2개, 나머지 항으로 확인
        p_ = (seq[2] - seq[1]) / (seq[1] - seq[0])
        q_ = seq[1] - p_ * seq[0]
        if all(seq[i + 1] == p_ * seq[i] + q_ for i in range(n - 1)):
            out.add(p_ * seq[-1] + q_)
    for with_r in (False, True):  # 2차 (상수항 포함은 6항 이상일 때만 확인 가능)
        need = 3 if with_r else 2
        if n < 2 + need + 1:
            continue
        # a(i+2) = p a(i+1) + q a(i) + r 를 처음 need개 식으로 푼다
        import numpy as _np
        A = [[float(seq[i + 1]), float(seq[i])] + ([1.0] if with_r else []) for i in range(need)]
        y = [float(seq[i + 2]) for i in range(need)]
        try:
            sol = _np.linalg.solve(_np.array(A), _np.array(y))
        except _np.linalg.LinAlgError:
            continue
        coef = [Fraction(x).limit_denominator(50) for x in sol]
        pp, qq, rr = coef[0], coef[1], (coef[2] if with_r else Fraction(0))
        if all(seq[i + 2] == pp * seq[i + 1] + qq * seq[i] + rr for i in range(n - 2)):
            out.add(pp * seq[-1] + qq * seq[-2] + rr)
    return out


def _periodic_ops_next(seq: list[Fraction]) -> set[Fraction]:
    """연산이 주기적으로 바뀌는 수열 (+p, ×m 번갈아 / 세 연산 반복)."""
    out = set()
    for period in (2, 3):
        if len(seq) < 2 * period + 1:
            continue
        ops = []
        for k in range(period):
            pairs = [(seq[i], seq[i + 1]) for i in range(k, len(seq) - 1, period)]
            adds = {b - a for a, b in pairs}
            muls = {b / a for a, b in pairs if a != 0} if all(a != 0 for a, _ in pairs) else set()
            if len(adds) == 1 and len(pairs) >= 2:
                ops.append(("+", adds.pop()))
            elif len(muls) == 1 and len(pairs) >= 2:
                ops.append(("*", muls.pop()))
            else:
                break
        if len(ops) == period:
            op, v = ops[(len(seq) - 1) % period]
            out.add(seq[-1] + v if op == "+" else seq[-1] * v)
    return out


def _interleaved_next(seq: list[Fraction]) -> set[Fraction]:
    """홀수 번째·짝수 번째가 따로 가는 수열 (각각 등차 또는 등비)."""
    if len(seq) < 6:
        return set()
    sub = seq[len(seq) % 2::2]  # 다음 항과 같은 갈래
    out = set()
    if (n := _poly_next(sub, 1)) is not None:
        out.add(n)
    if all(x != 0 for x in sub[:-1]) and len({b / a for a, b in zip(sub, sub[1:])}) == 1:
        out.add(sub[-1] * sub[-1] / sub[-2])
    return out


def series_predictions(shown: list[int]) -> set[Fraction]:
    """보여 준 항을 모두 설명하는 '그럴듯한 다른 규칙'들이 예측하는 다음 수 모음."""
    seq = [Fraction(x) for x in shown]
    preds = set(_linear_rec_next(seq)) | _periodic_ops_next(seq) | _interleaved_next(seq)
    if (n := _poly_next(seq)) is not None:
        preds.add(n)
    diffs = [b - a for a, b in zip(seq, seq[1:])]  # 차이 수열이 다시 규칙을 이루는 경우
    for d in ({_poly_next(diffs)} | _linear_rec_next(diffs)) - {None}:
        preds.add(seq[-1] + d)
    if all(x != 0 for x in seq):  # 비율 수열이 규칙을 이루는 경우 (계승형 등)
        ratios = [b / a for a, b in zip(seq, seq[1:])]
        if (r := _poly_next(ratios, 1)) is not None:
            preds.add(seq[-1] * r)
    return preds


def series_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    kind = pick_variant(spec, SERIES_LEVELS[spec["level"]])
    for _ in range(500):
        # 규칙(난이도)은 그대로 두고, 보여 줄 숫자가 다른 규칙으로도 설명되어 답이 갈리면 숫자만 다시 뽑는다
        shown, ans, wrong, why = _series(kind, rng)
        if series_predictions(shown) <= {Fraction(ans)}:
            break
    else:
        raise RuntimeError(f"[{item.id}] 답이 하나인 수열을 만들지 못함 ({kind})")
    choices, idx = _options(ans, wrong, rng)
    return replace(item, prompt=f"{', '.join(map(str, shown))}, ( )", choices=choices, answer=idx,
                   explanation=f"{why} 따라서 다음 수는 {ans:,}입니다.",
                   params={**item.params, "rule": kind, "shown": shown, "value": ans})


# ---------------------------------------------------------------- 수 행렬

NM_RULES = {
    # 이름: (계산식, 설명, a 범위, b 범위)
    "sum": (lambda a, b: a + b, "각 행에서 앞의 두 수를 더하면 세 번째 수가 됩니다.", (2, 30), (2, 30)),
    "diff": (lambda a, b: a - b, "각 행에서 첫째 수에서 둘째 수를 빼면 세 번째 수가 됩니다.", (20, 60), (2, 19)),
    "prod": (lambda a, b: a * b, "각 행에서 앞의 두 수를 곱하면 세 번째 수가 됩니다.", (2, 9), (2, 9)),
    "double_sum": (lambda a, b: (a + b) * 2, "각 행에서 앞의 두 수를 더한 뒤 2를 곱하면 세 번째 수가 됩니다.", (2, 15), (2, 15)),
    "prod_minus": (lambda a, b: a * b - a, "각 행에서 (첫째 × 둘째) − 첫째 가 세 번째 수입니다.", (2, 9), (2, 9)),
    "square_plus": (lambda a, b: a * a + b, "각 행에서 첫째 수의 제곱에 둘째 수를 더하면 세 번째 수가 됩니다.", (2, 9), (1, 9)),
    "twice_plus": (lambda a, b: 2 * a + b, "각 행에서 첫째 수의 2배에 둘째 수를 더하면 세 번째 수가 됩니다.", (2, 20), (1, 20)),
    "diff_triple": (lambda a, b: (a - b) * 3, "각 행에서 두 수의 차에 3을 곱하면 세 번째 수가 됩니다.", (10, 30), (1, 9)),
    "sq_sum": (lambda a, b: a * a + b * b, "각 행에서 두 수를 각각 제곱해 더하면 세 번째 수가 됩니다.", (1, 9), (1, 9)),
    "sq_diff": (lambda a, b: a * a - b * b, "각 행에서 첫째 수의 제곱에서 둘째 수의 제곱을 빼면 세 번째 수가 됩니다.",
                (5, 12), (1, 4)),
    "ab_plus": (lambda a, b: a * b + a + b, "각 행에서 두 수의 곱에 두 수를 모두 더하면 세 번째 수가 됩니다.", (2, 9), (2, 9)),
    "diff_sq": (lambda a, b: (a - b) ** 2, "각 행에서 두 수의 차를 제곱하면 세 번째 수가 됩니다.", (10, 20), (1, 9)),
    "sum_sq": (lambda a, b: (a + b) ** 2, "각 행에서 두 수의 합을 제곱하면 세 번째 수가 됩니다.", (1, 6), (1, 6)),
}
NM_LEVELS = {
    2: ["sum", "diff", "prod", "twice_plus", "sum", "prod"],
    3: ["double_sum", "prod_minus", "square_plus", "diff_triple", "twice_plus", "prod_minus"],
    4: ["sq_sum", "sq_diff", "ab_plus", "diff_sq", "sum_sq", "sq_sum"],
}


def _rival_family() -> list:
    """예시 행이 '다른 그럴듯한 규칙'으로도 설명되는지 검사할 때 쓰는 규칙 모음.

    출제용 규칙만 비교하면 a×(b+1)처럼 목록에 없는 규칙으로도 풀리는 문제를 걸러내지 못한다.
    """
    fam = []
    for p in (-1, 0, 1, 2):
        for q in (-1, 0, 1, 2):
            for r in range(-3, 4):
                fam.append(lambda a, b, p=p, q=q, r=r: a * b + p * a + q * b + r)      # ab + pa + qb + r
    for p in range(-2, 3):
        for r in range(-3, 4):
            fam.append(lambda a, b, p=p, r=r: a * a + p * b + r)                     # a² + pb + r
            fam.append(lambda a, b, p=p, r=r: b * b + p * a + r)                     # b² + pa + r
    for p in range(-2, 3):
        for q in range(-2, 3):
            fam.append(lambda a, b, p=p, q=q: (a + p) * (b + q))                     # (a+p)(b+q)
    for p in range(0, 4):
        for q in range(-3, 4):
            for r in range(-5, 6):
                fam.append(lambda a, b, p=p, q=q, r=r: p * a + q * b + r)            # 일차식
    for k in range(1, 5):
        for r in range(-3, 4):
            fam.append(lambda a, b, k=k, r=r: (a + b) * k + r)
            fam.append(lambda a, b, k=k, r=r: (a - b) * k + r)
    fam += [lambda a, b: a * a + b * b, lambda a, b: a * a - b * b, lambda a, b: (a + b) ** 2,
            lambda a, b: (a - b) ** 2, lambda a, b: a ** 3 - b, lambda a, b: a * b * 2]
    return fam


RIVALS = _rival_family()


def unambiguous(f, examples: list[tuple[int, int]], query: tuple[int, int], extra=()) -> bool:
    """예시에 들어맞는 모든 규칙이 질문에도 같은 답을 내는가. 두 수가 같은 예시는 규칙 구별을 막으므로 금지."""
    if any(a == b for a, b in examples + [query]):
        return False
    answer = f(*query)
    for g in [*RIVALS, *extra]:
        if all(g(a, b) == f(a, b) for a, b in examples) and g(*query) != answer:
            return False
    return True


def _number_grid_svg(rows: list[list]) -> str:
    cell, gap = 72, 6
    size = 3 * cell + 2 * gap
    height = len(rows) * cell + (len(rows) - 1) * gap
    body = ""
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            x, y = c * (cell + gap), r * (cell + gap)
            dash = ' stroke-dasharray="6 5"' if v == "?" else ""
            body += (f'<rect x="{x + 1}" y="{y + 1}" width="{cell - 2}" height="{cell - 2}" rx="6" fill="none" '
                     f'stroke="#6b7280" stroke-width="1.5"{dash}/>'
                     f'<text x="{x + cell / 2}" y="{y + cell / 2 + 10}" text-anchor="middle" font-size="28" '
                     f'font-family="sans-serif" font-weight="600" fill="#111827">{v}</text>')
    return _svg(size, height, body)


def number_matrix_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    name = pick_variant(spec, NM_LEVELS[spec["level"]])
    f, why, ra, rb = NM_RULES[name]
    library = [g for g, *_ in NM_RULES.values()]
    while True:  # 예시 3행 + 질문 1행. 예시에 맞는 다른 규칙이 다른 답을 내면 다시 뽑는다
        pairs = [(rng.randint(*ra), rng.randint(*rb)) for _ in range(4)]
        vals = [f(a, b) for a, b in pairs]
        if len(set(pairs)) == 4 and all(v > 0 for v in vals) and unambiguous(f, pairs[:3], pairs[3], library):
            break
    rows = [[a, b, v] for (a, b), v in zip(pairs, vals)]
    ans = rows[3][2]
    a, b = pairs[3]
    rows[3][2] = "?"
    wrong = [g(a, b) for n, (g, *_) in NM_RULES.items() if n != name]
    wrong = sorted({w for w in wrong if 0 < w != ans}, key=lambda w: abs(w - ans))
    choices, idx = _options(ans, wrong, rng)
    return replace(item, stem_svg=_number_grid_svg(rows), choices=choices, answer=idx,
                   explanation=f"{why} 따라서 {a}, {b} 다음에는 {josa(ans, '이/가')} 들어갑니다.",
                   params={**item.params, "rule": name, "examples": pairs[:3], "query": pairs[3], "value": ans})


# ---------------------------------------------------------------- 연산 기호 추론

OPS = {
    "2a+b": (lambda a, b: 2 * a + b, "앞 수의 2배에 뒤 수를 더한"),
    "ab+1": (lambda a, b: a * b + 1, "두 수를 곱하고 1을 더한"),
    "a2-b": (lambda a, b: a * a - b, "앞 수의 제곱에서 뒤 수를 뺀"),
    "2(a+b)": (lambda a, b: 2 * (a + b), "두 수를 더해 2를 곱한"),
    "a+b2": (lambda a, b: a + b * b, "앞 수에 뒤 수의 제곱을 더한"),
    "ab-a": (lambda a, b: a * b - a, "두 수를 곱하고 앞 수를 뺀"),
    "a+b+ab": (lambda a, b: a + b + a * b, "두 수의 합에 두 수의 곱을 더한"),
    "3a-b": (lambda a, b: 3 * a - b, "앞 수의 3배에서 뒤 수를 뺀"),
    "a+2b": (lambda a, b: a + 2 * b, "앞 수에 뒤 수의 2배를 더한"),
    "a+b+3": (lambda a, b: a + b + 3, "두 수를 더하고 3을 더한"),
    "a+b-1": (lambda a, b: a + b - 1, "두 수를 더하고 1을 뺀"),
    "3a+b": (lambda a, b: 3 * a + b, "앞 수의 3배에 뒤 수를 더한"),
    "a2+b2": (lambda a, b: a * a + b * b, "두 수를 각각 제곱해 더한"),
    "a2-ab": (lambda a, b: a * a - a * b, "앞 수의 제곱에서 두 수의 곱을 뺀"),
    "2ab-b": (lambda a, b: 2 * a * b - b, "두 수의 곱의 2배에서 뒤 수를 뺀"),
    "(a-b)2": (lambda a, b: (a - b) ** 2, "두 수의 차를 제곱한"),
    "ab+b2": (lambda a, b: a * b + b * b, "두 수의 곱에 뒤 수의 제곱을 더한"),
}
OP_LEVELS = {
    1: ["a+2b", "a+b+3", "a+b-1", "3a+b", "2a+b", "a+2b"],
    2: ["ab+1", "a2-b", "2(a+b)", "a+b2", "ab-a", "3a-b"],
    3: ["a2+b2", "a2-ab", "2ab-b", "(a-b)2", "ab+b2", "a+b+ab"],
}
SYMBOLS = ["★", "◆", "♣", "▲", "●", "◎"]


def operator_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    name = pick_variant(spec, OP_LEVELS[spec.get("level", 2)])
    f, why = OPS[name]
    sym = SYMBOLS[spec.get("form", 0) % len(SYMBOLS)]
    while True:
        ex = [(rng.randint(2, 7), rng.randint(1, 6)) for _ in range(3)]
        q = (rng.randint(3, 8), rng.randint(2, 6))
        library = [g for g, _ in OPS.values()]
        if len(set(ex + [q])) == 4 and f(*q) > 0 and unambiguous(f, ex, q, library):
            break
    ans = f(*q)
    wrong = sorted({g(*q) for g, _ in OPS.values()} - {ans}, key=lambda w: abs(w - ans))
    choices, idx = _options(ans, wrong, rng)
    lines = "  ".join(f"{a} {sym} {b} = {f(a, b)}" for a, b in ex)
    return replace(item, prompt=f"{lines}\n\n그렇다면 {q[0]} {sym} {q[1]} = ( )", choices=choices, answer=idx,
                   explanation=f"{sym}는 {why} 값입니다. 따라서 {q[0]} {sym} {q[1]} = {ans:,}입니다.",
                   params={**item.params, "rule": name, "examples": ex, "query": q, "value": ans})


# ---------------------------------------------------------------- 자료 해석

STORES = ["가", "나", "다", "라"]
DATA_LEVELS = {1: ["total", "max_diff", "average", "total", "max_diff", "average"],
               2: ["max_rate", "min_rate", "share", "max_rate", "share", "min_rate"]}


def _table_svg(header: list[str], rows: list[list]) -> str:
    cw, rh = 110, 40
    w, h = cw * len(header), rh * (len(rows) + 1)
    body = f'<rect x="0" y="0" width="{w}" height="{rh}" fill="#eef2ff"/>'
    for r, row in enumerate([header, *rows]):
        for c, v in enumerate(row):
            weight = "700" if r == 0 or c == 0 else "400"
            body += (f'<text x="{c * cw + cw / 2}" y="{r * rh + 26}" text-anchor="middle" font-size="17" '
                     f'font-family="sans-serif" font-weight="{weight}" fill="#111827">{v}</text>')
    for r in range(len(rows) + 2):
        body += f'<line x1="0" y1="{r * rh}" x2="{w}" y2="{r * rh}" stroke="#9ca3af"/>'
    body += f'<line x1="{cw}" y1="0" x2="{cw}" y2="{h}" stroke="#9ca3af"/>'
    return _svg(w, h, body)


def data_item(item: Item) -> Item:
    spec = item.svg
    rng = random.Random(spec["seed"])
    kind = pick_variant(spec, DATA_LEVELS[spec.get("level", 2)])
    while True:
        jan = [rng.randrange(40, 160, 10) for _ in STORES]
        feb = [j + rng.randrange(-30, 70, 10) for j in jan]
        rates = [(f - j) / j * 100 for j, f in zip(jan, feb)]
        diffs = [f - j for j, f in zip(jan, feb)]
        if min(feb) > 0 and len(set(rates)) == 4 and len(set(diffs)) == 4:
            break
    rows = [[f"{s} 매장", j, f] for s, j, f in zip(STORES, jan, feb)]
    names = [f"{s} 매장" for s in STORES]
    if kind in ("max_rate", "min_rate"):
        pick = max if kind == "max_rate" else min
        i = rates.index(pick(rates))
        word = "가장 높은" if kind == "max_rate" else "가장 낮은"
        q = f"1월 대비 2월 판매량의 증가율이 {word} 매장은? (줄어든 경우 증가율은 음수)"
        # 증가'량'으로 착각하면 고르게 되는 매장이 오답 중 하나가 되도록 순서 유지
        choices, idx = names, i
        why = "증가율 = (2월 − 1월) ÷ 1월. " + ", ".join(f"{n} {r:+.0f}%" for n, r in zip(names, rates))
    elif kind == "max_diff":
        i = diffs.index(max(diffs))
        q = "1월 대비 2월 판매량이 가장 많이 늘어난 매장은?"
        choices, idx = names, i
        why = ", ".join(f"{n} {d:+}개" for n, d in zip(names, diffs))
    else:
        if kind == "total":
            ans = sum(feb)
            q = "2월 네 매장의 판매량 합계는? (단위: 개)"
            wrong = [sum(jan), ans + 10, ans - 10]
            why = " + ".join(map(str, feb)) + f" = {ans}"
        elif kind == "average":
            tot = sum(jan) + sum(feb)
            if tot % 8:
                return data_item(replace(item, svg={**spec, "seed": spec["seed"] + 1}))
            ans = tot // 8
            q = "1월과 2월을 합친 매장당 월평균 판매량은? (단위: 개)"
            wrong = [sum(feb) // 4, sum(jan) // 4, ans + 5]
            why = f"두 달 합계 {tot}개를 4개 매장 × 2개월 = 8로 나누면 {ans}개입니다"
        else:  # share
            i = rng.randrange(4)
            tot = sum(feb)
            if feb[i] * 100 % tot:
                return data_item(replace(item, svg={**spec, "seed": spec["seed"] + 1}))
            ans = feb[i] * 100 // tot
            q = f"2월 전체 판매량 중 {names[i]}이 차지하는 비율은? (단위: %)"
            wrong = [jan[i] * 100 // sum(jan), ans + 5, ans - 5]
            why = f"{feb[i]} ÷ {tot} × 100 = {ans}%"
        choices, idx = _options(ans, wrong, rng, spread=5)
        return replace(item, stem_svg=_table_svg(["", "1월", "2월"], rows), prompt=f"표는 매장별 판매량(개)이다. {q}",
                       choices=choices, answer=idx, explanation=why + ".", params={**item.params, "rule": kind})
    return replace(item, stem_svg=_table_svg(["", "1월", "2월"], rows), prompt=f"표는 매장별 판매량(개)이다. {q}",
                   choices=choices, answer=idx, explanation=why + ".", params={**item.params, "rule": kind})
