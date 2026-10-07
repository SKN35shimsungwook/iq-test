"""문항은행 로드·검증·검사지 구성.

- items/*.json: 직접 작성한 문항 (generated.json 제외)
- items/generated.json: 생성기 슬롯 정의. 슬롯마다 forms개의 동형 문항(a, b, c, ...)으로 펼친다.
"""

from __future__ import annotations

import json
import random
import string
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

from core.figures import materialize
from core.schema import BLUEPRINT, MAX_SAME_TYPE, MIN_DOMAIN_POOL, MIN_FORMS, SLOTS, Domain, Item, ItemFormat, Mode

ITEMS_DIR = Path(__file__).resolve().parent.parent / "items"
GENERATED = "generated.json"


def form_seed(slot: str, index: int) -> int:
    return zlib.crc32(f"{slot}:{index}".encode())


def expand_generated(entries: list[dict]) -> list[Item]:
    items = []
    for e in entries:
        slot = e["slot"]
        for i in range(e["forms"]):
            svg = {"generator": e["generator"], "seed": form_seed(slot, i), "form": i,
                   "pool_seed": zlib.crc32(slot.encode()), **e.get("params", {})}
            items.append(materialize(Item.from_dict({
                "id": f"{slot}{string.ascii_lowercase[i]}", "slot": slot, "prompt": e["prompt"],
                "answer": None, "svg": svg, "expected_p": e["expected_p"],
            })))
    return items


def balance_answer_positions(items: list[Item]) -> list[Item]:
    """정답 위치가 한쪽으로 몰리면 찍기가 유리해진다 (직접 작성 문항은 작성자 습관으로 특히 그렇다).

    슬롯마다 동형 문항이 정답 위치 A~D를 돌아가며 갖도록 정답 보기만 옮긴다 (오답 순서는 유지).
    """
    out, by_slot = [], defaultdict(list)
    for it in items:
        by_slot[it.slot].append(it)
    for slot, group in by_slot.items():
        order = random.Random(zlib.crc32(slot.encode())).sample(range(4), 4)
        for k, it in enumerate(sorted(group, key=lambda x: x.id)):
            if it.format is not ItemFormat.MCQ:
                out.append(it)
                continue
            target = order[k % 4]
            rest = [c for i, c in enumerate(it.choices) if i != it.answer]
            choices = rest[:target] + [it.choices[it.answer]] + rest[target:]
            out.append(replace(it, choices=choices, answer=target))
    return out


def load_items(items_dir: Path = ITEMS_DIR) -> list[Item]:
    items: list[Item] = []
    for path in sorted(items_dir.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if path.name == GENERATED:
            items.extend(balance_answer_positions(expand_generated(data)))
            continue
        written = []
        for d in data:
            item = Item.from_dict(d)
            if item.svg and "generator" in item.svg:
                item = materialize(item)
            written.append(item)
        items.extend(balance_answer_positions(written))
    return items


def validate_bank(items: list[Item]) -> list[str]:
    """문항은행 전체 검증: 개별 문항 오류 + ID 중복 + 슬롯별 동형 문항 수 부족."""
    errors = [f"[{it.id}] {e}" for it in items for e in it.validate()]

    counts = Counter(it.id for it in items)
    errors += [f"[{i}] 중복 ID" for i, n in counts.items() if n > 1]

    by_slot = Counter(it.slot for it in items)
    mcq_slots = {it.slot for it in items if it.format is ItemFormat.MCQ}
    for slot_id, slot in SLOTS.items():
        need = MIN_FORMS if slot_id in mcq_slots or slot_id not in by_slot else 1
        if by_slot[slot_id] < need:
            errors.append(f"[{slot_id}] {slot.subtype} 동형 {by_slot[slot_id]}개 / 필요 {need}개")

    pool = Counter(it.domain for it in items if it.format is ItemFormat.MCQ)
    for domain in {it.domain for it in items if it.format is ItemFormat.MCQ}:
        if pool[domain] < MIN_DOMAIN_POOL:
            errors.append(f"[{domain.value}] 문항 풀 {pool[domain]}개 / 필요 {MIN_DOMAIN_POOL}개")
    return errors


def validate_blueprint() -> list[str]:
    """구성표 규칙.

    - 경로(1단계 + 묶음)마다 같은 유형은 MAX_SAME_TYPE번 이하
    - 빠른 검사 경로는 모두 다른 유형
    - 한 계획 안의 경로 길이는 모두 같음 (묶음에 따라 문항 수가 달라지지 않게)
    """
    errors = []
    for domain, spec in BLUEPRINT.items():
        for mode in Mode:
            plan = spec.plan_for(mode)
            if plan is None:
                continue
            paths = plan.paths()
            if len({len(p) for p in paths.values()}) > 1:
                errors.append(f"[{domain.value}/{mode.value}] 경로 길이가 다름")
            for name, path in paths.items():
                counts = Counter(SLOTS[x].subtype for x in path)
                limit = 1 if mode is Mode.QUICK else MAX_SAME_TYPE
                errors += [f"[{domain.value}/{mode.value}/{name}] {t} {n}회" for t, n in counts.items() if n > limit]
                if len(set(path)) != len(path):
                    errors.append(f"[{domain.value}/{mode.value}/{name}] 같은 슬롯이 한 경로에 두 번")
    return errors


def items_by_slot(items: list[Item]) -> dict[str, list[Item]]:
    out: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        out[it.slot].append(it)
    return out


@dataclass
class DomainForm:
    """한 영역의 검사지: 1단계 문항과, 정답률에 따라 이어질 묶음 후보 셋."""
    stage1: list[Item]
    panels: dict[str, list[Item]] = field(default_factory=dict)

    def path(self, panel: str | None) -> list[Item]:
        return self.stage1 + (self.panels.get(panel, []) if panel else [])


def build_form(items: list[Item], seed: int, mode: Mode = Mode.FULL,
               exclude: set[str] | frozenset[str] = frozenset()) -> dict[Domain, DomainForm]:
    """시드로 슬롯마다 동형 문항을 골라 검사지를 만든다.

    - exclude: 앞 라운드에서 이미 본 문항 ID (추가 라운드가 겹치지 않게)
    - 한 라운드 안에서도 같은 문항이 두 번 뽑히지 않는다
    - 문항이 없는 슬롯은 건너뛴다 (개발 중 부분 문항은행 허용)
    """
    rng = random.Random(seed)
    pool = items_by_slot(items)
    taken = set(exclude)

    def draw(slot_ids) -> list[Item]:
        out = []
        for sid in slot_ids:
            cands = [it for it in pool.get(sid, []) if it.id not in taken]
            if not cands:  # 동형을 다 썼으면 (라운드가 너무 많을 때) 본 문항도 허용
                cands = [it for it in pool.get(sid, []) if it.id not in {o.id for o in out}]
            if cands:
                pick = rng.choice(sorted(cands, key=lambda it: it.id))
                taken.add(pick.id)
                out.append(pick)
        return out

    form = {}
    for domain, spec in BLUEPRINT.items():
        plan = spec.plan_for(mode)
        if plan is None:
            continue
        form[domain] = DomainForm(draw(plan.stage1), {p: draw(sl) for p, sl in plan.panels.items()})
    return form
