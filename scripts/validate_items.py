"""문항은행 검증: python scripts/validate_items.py [--strict]

--strict 이면 슬롯별 동형 문항 수 부족도 실패로 처리한다 (배포 전 확인용).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.item_bank import items_by_slot, load_items, validate_blueprint, validate_bank  # noqa: E402
from core.schema import BLUEPRINT, MIN_FORMS  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
strict = "--strict" in sys.argv
items = load_items()
shortage = [e for e in validate_bank(items) if "필요" in e]
errors = validate_blueprint() + [e for e in validate_bank(items) if "필요" not in e]
if strict:
    errors += shortage

pool = items_by_slot(items)
print(f"문항 {len(items)}개 (4지선다 슬롯당 최소 {MIN_FORMS}개)")
for domain, spec in BLUEPRINT.items():
    print(f"\n{spec.label} ({domain.value})")
    for s in spec.slots:
        have = len(pool.get(s.id, []))
        mark = "빠른" if s.quick else "    "
        print(f"  {s.id:<7} {mark} {s.subtype:<14} 난이도{s.difficulty}  동형 {have}")

if shortage and not strict:
    print(f"\n동형 부족 슬롯 {len(shortage)}개 (--strict 에서만 실패)")
if errors:
    print(f"\n오류 {len(errors)}건")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("\n통과")
