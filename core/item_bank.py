"""items/*.json 문항은행 로드·검증·검사지 구성."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from core.schema import TEST_PLAN, Domain, Item

ITEMS_DIR = Path(__file__).resolve().parent.parent / "items"


def load_items(items_dir: Path = ITEMS_DIR) -> list[Item]:
    items: list[Item] = []
    for path in sorted(items_dir.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            items.extend(Item.from_dict(d) for d in json.load(f))
    return items


def validate_bank(items: list[Item]) -> list[str]:
    """문항은행 전체 검증: 개별 문항 오류 + ID 중복 + 슬롯 수 부족."""
    errors = [f"[{it.id}] {e}" for it in items for e in it.validate()]

    seen: set[str] = set()
    for it in items:
        if it.id in seen:
            errors.append(f"[{it.id}] 중복 ID")
        seen.add(it.id)

    slots = slots_by_domain(items)
    for domain, spec in TEST_PLAN.items():
        have = len(slots.get(domain, {}))
        if have < spec.slots:
            errors.append(f"[{domain.value}] 슬롯 {have}개 / 필요 {spec.slots}개")
    return errors


def slots_by_domain(items: list[Item]) -> dict[Domain, dict[str, list[Item]]]:
    out: dict[Domain, dict[str, list[Item]]] = defaultdict(lambda: defaultdict(list))
    for it in items:
        out[it.domain][it.slot].append(it)
    return out


def build_form(items: list[Item], seed: int) -> dict[Domain, list[Item]]:
    """시드로 슬롯마다 동형 문항 1개를 골라 검사지를 만든다.

    영역 내 순서는 슬롯 ID 순(= 난이도 점진 상승 순으로 작성)으로 고정한다.
    문항이 부족한 영역은 있는 만큼만 담는다 (개발 중 부분 문항은행 허용).
    """
    rng = random.Random(seed)
    slots = slots_by_domain(items)
    form: dict[Domain, list[Item]] = {}
    for domain, spec in TEST_PLAN.items():
        chosen = [rng.choice(slots[domain][s]) for s in sorted(slots.get(domain, {}))]
        form[domain] = chosen[: spec.slots]
    return form
