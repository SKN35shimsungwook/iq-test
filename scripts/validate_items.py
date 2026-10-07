"""문항은행 검증: python scripts/validate_items.py [--strict]

--strict 이면 영역별 슬롯 수 부족도 실패로 처리한다 (배포 전 확인용).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.item_bank import load_items, slots_by_domain, validate_bank  # noqa: E402
from core.schema import TEST_PLAN  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
strict = "--strict" in sys.argv
items = load_items()
errors = validate_bank(items)
if not strict:
    errors = [e for e in errors if "슬롯" not in e or "필요" not in e]

slots = slots_by_domain(items)
print(f"문항 {len(items)}개")
for domain, spec in TEST_PLAN.items():
    have = slots.get(domain, {})
    forms = sum(len(v) for v in have.values())
    print(f"  {spec.label:<5} 슬롯 {len(have):>2}/{spec.slots}  문항 {forms}")

if errors:
    print(f"\n오류 {len(errors)}건")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("\n통과")
