"""문항 검토용 HTML 생성: python scripts/render_review.py → review/items_review.html

모든 문항(동형 포함)을 영역·슬롯 순으로 보여주고 정답 보기를 강조한다.
"""

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.item_bank import load_items  # noqa: E402
from core.item_bank import items_by_slot  # noqa: E402
from core.schema import BLUEPRINT, DIFFICULTY_LABELS, ItemFormat  # noqa: E402

OUT = ROOT / "review" / "items_review.html"
LETTERS = "ABCD"

CSS = """
body{font-family:-apple-system,'Malgun Gothic',sans-serif;max-width:960px;margin:24px auto;padding:0 16px;
     color:#111827;background:#f9fafb}
h2{margin-top:40px;border-bottom:2px solid #4F46E5;padding-bottom:6px}
h3{margin:28px 0 4px;font-size:16px;color:#374151}
.item{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin:12px 0}
.meta{font-size:13px;color:#6b7280;margin-bottom:6px}
.id{font-family:monospace;font-weight:700;color:#4F46E5}
.prompt{font-size:17px;margin:8px 0 12px}
.stem svg{max-width:320px;border:1px solid #e5e7eb;border-radius:6px}
.choices{display:flex;flex-wrap:wrap;gap:10px;margin-top:10px}
.choice{border:2px solid #e5e7eb;border-radius:8px;padding:8px 12px;min-width:90px}
.choice svg{width:100px;display:block}
.choice.ok{border-color:#16a34a;background:#f0fdf4}
.choice b{color:#6b7280;margin-right:6px}
.exp{margin-top:10px;font-size:14px;background:#eef2ff;border-radius:6px;padding:8px 10px}
.params{font-family:monospace;font-size:13px}
"""


def render_item(it) -> str:
    meta = (f'<div class="meta"><span class="id">{it.id}</span> · {it.subtype} · '
            f'{DIFFICULTY_LABELS[it.difficulty]} · 예상 정답률 {it.expected_p:.0%} · v{it.version}</div>')
    body = f'<div class="prompt">{html.escape(it.prompt)}</div>'
    if it.stem_svg:
        body += f'<div class="stem">{it.stem_svg}</div>'
    if it.format is ItemFormat.MCQ:
        cells = []
        for i, c in enumerate(it.choices):
            content = c if str(c).startswith("<svg") else html.escape(str(c))
            cls = "choice ok" if i == it.answer else "choice"
            cells.append(f'<div class="{cls}"><b>{LETTERS[i]}</b>{content}</div>')
        body += f'<div class="choices">{"".join(cells)}</div>'
    else:
        body += f'<div class="params">{html.escape(str(it.params))}</div>'
    if it.explanation:
        body += f'<div class="exp">{html.escape(it.explanation)}</div>'
    return f'<div class="item">{meta}{body}</div>'


items = load_items()
pool = items_by_slot(items)
sections = []
for domain, spec in BLUEPRINT.items():
    sections.append(f"<h2>{spec.label} ({domain.value})</h2>")
    for s in spec.slots:
        group = sorted(pool.get(s.id, []), key=lambda it: it.id)
        quick = " · 빠른 검사 포함" if s.quick else ""
        sections.append(f'<h3>{s.id} · {s.subtype} · {DIFFICULTY_LABELS[s.difficulty]}{quick} '
                        f'— 동형 {len(group)}개</h3>')
        sections.extend(render_item(it) for it in group)

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(
    f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>문항 검토</title>'
    f'<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head>'
    f'<body><h1>종합사고지수 문항 검토 ({len(items)}문항)</h1>'
    f'<p>초록 테두리가 정답입니다. 슬롯마다 동형 문항 중 하나만 무작위로 출제됩니다.</p>'
    f'{"".join(sections)}</body></html>',
    encoding="utf-8",
)
print(OUT)
