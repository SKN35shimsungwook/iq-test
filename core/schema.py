"""문항 스키마와 검사 구성(영역·문항 수·제한시간) 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Domain(str, Enum):
    GF = "gf"    # 유동추론
    GC = "gc"    # 언어
    GQ = "gq"    # 수리
    GV = "gv"    # 시공간
    GWM = "gwm"  # 작업기억
    GS = "gs"    # 처리속도


class ItemFormat(str, Enum):
    MCQ = "mcq"                      # 4지선다 (텍스트 또는 SVG 보기)
    DIGIT_SPAN = "digit_span"        # 숫자 순차 제시 후 입력 (정순·역순·정렬)
    SPATIAL_SPAN = "spatial_span"    # 격자 칸이 순서대로 켜진 뒤 같은 순서로 누르기
    SYMBOL_CODING = "symbol_coding"  # 기호→숫자 변환 블록


class Mode(str, Enum):
    QUICK = "quick"  # 영역별 서로 다른 유형 4문항, 종합지수 위주
    FULL = "full"    # 영역별 8~10문항 + 처리속도, 영역 분석까지


MODE_LABELS = {Mode.QUICK: "빠른 검사", Mode.FULL: "정밀 검사"}
MIN_FORMS = 6       # 4지선다 슬롯당 최소 동형 문항 수
MAX_SAME_TYPE = 2   # 한 검사지·한 영역 안에서 같은 유형 최대 출제 수
MIN_DOMAIN_POOL = 30  # 4지선다 영역당 최소 문항 풀 크기


@dataclass(frozen=True)
class SlotSpec:
    id: str          # 예: "gf-04"
    subtype: str     # 문항 유형
    difficulty: int  # 1~3
    quick: bool = False  # 빠른 검사에도 출제


@dataclass(frozen=True)
class DomainSpec:
    label: str
    slots: tuple[SlotSpec, ...]  # 출제 순서대로
    time_full: int               # 영역 제한시간(초), 0이면 문항 자체 타이밍
    time_quick: int = 0
    weight: float = 1.0          # 종합지수 가중치

    def slots_for(self, mode: Mode) -> tuple[SlotSpec, ...]:
        return self.slots if mode is Mode.FULL else tuple(s for s in self.slots if s.quick)

    def time_for(self, mode: Mode) -> int:
        return self.time_full if mode is Mode.FULL else self.time_quick


def _slots(prefix: str, rows: list[tuple[str, int, bool]]) -> tuple[SlotSpec, ...]:
    return tuple(SlotSpec(f"{prefix}-{i:02d}", t, d, q) for i, (t, d, q) in enumerate(rows, 1))


# 검사 구성표 (영역 순서 = 출제 순서). 영역 경계:
#   유동추론 = 도형만, 수리 = 숫자만, 언어 = 어휘·지식 기반, 시공간 = 공간 조작
BLUEPRINT: dict[Domain, DomainSpec] = {
    Domain.GF: DomainSpec("유동추론", _slots("gf", [
        ("matrix", 1, True), ("sequence", 1, False), ("odd_one_out", 1, False),
        ("sequence", 2, True), ("analogy", 2, False), ("odd_one_out", 2, True),
        ("transform", 2, False), ("matrix", 3, False), ("transform", 3, True), ("analogy", 3, False),
    ]), time_full=9 * 60, time_quick=4 * 60),
    Domain.GC: DomainSpec("언어", _slots("gc", [
        ("synonym", 1, True), ("analogy", 1, False), ("category", 1, False), ("completion", 2, True),
        ("antonym", 2, False), ("category", 2, True), ("synonym", 3, False), ("analogy", 3, True),
    ]), time_full=5 * 60, time_quick=150),
    Domain.GQ: DomainSpec("수리", _slots("gq", [
        ("series", 1, True), ("applied", 1, False), ("number_matrix", 2, True), ("data", 2, False),
        ("series", 2, False), ("operator", 2, True), ("number_matrix", 3, False), ("applied", 3, True),
    ]), time_full=7 * 60, time_quick=4 * 60),
    Domain.GV: DomainSpec("시공간", _slots("gv", [
        ("rotation", 1, True), ("paper_fold", 1, False), ("cube_net", 2, True), ("assembly", 2, False),
        ("rotation", 2, False), ("paper_fold", 2, True), ("cube_net", 3, False), ("assembly", 3, True),
    ]), time_full=7 * 60, time_quick=4 * 60),
    Domain.GWM: DomainSpec("작업기억", _slots("gwm", [
        ("forward", 1, True), ("spatial", 1, False), ("backward", 1, False), ("sorting", 2, True),
        ("forward", 2, False), ("backward", 2, True), ("spatial", 3, True), ("sorting", 3, False),
    ]), time_full=0),
    Domain.GS: DomainSpec("처리속도", _slots("gs", [("symbol_coding", 2, False)]), time_full=90),
}

SLOTS: dict[str, SlotSpec] = {s.id: s for spec in BLUEPRINT.values() for s in spec.slots}

DIFFICULTY_LABELS = {1: "쉬움", 2: "보통", 3: "어려움"}


@dataclass
class Item:
    id: str                  # 예: "gf-01a" (슬롯 gf-01의 동형 a)
    domain: Domain
    slot: str                # 동형 문항끼리 공유하는 슬롯 ID
    format: ItemFormat
    subtype: str             # 예: matrix, vocabulary, series, rotation
    difficulty: int          # 1~3
    prompt: str
    answer: Any              # MCQ: 보기 인덱스(0~3), digit_span: 정답 문자열 등
    choices: list[Any] = field(default_factory=list)  # 텍스트 또는 SVG 스펙
    svg: dict | None = None  # 도형 생성기 스펙 {"generator": "matrix"|"rotation", "seed": ...}
    stem_svg: str = ""       # 생성기가 만든 문제 그림 (로드 시 채워짐)
    params: dict = field(default_factory=dict)        # 형식별 설정, verify: 정답 계산식
    explanation: str = ""
    expected_p: float = 0.5  # 예상 정답률 (규준 데이터 전 가정 규준에 사용)
    version: int = 1
    irt_a: float | None = None
    irt_b: float | None = None
    irt_c: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        """영역·유형·난이도는 생략하면 구성표의 슬롯 정의에서 채운다."""
        d = dict(d)
        slot = SLOTS.get(d["slot"])
        if slot:
            d.setdefault("domain", d["slot"].split("-")[0])
            d.setdefault("subtype", slot.subtype)
            d.setdefault("difficulty", slot.difficulty)
        d["domain"] = Domain(d["domain"])
        d["format"] = ItemFormat(d.get("format", "mcq"))
        return cls(**d)

    def validate(self) -> list[str]:
        """문항 자체의 형식 오류 목록 (비어 있으면 통과)."""
        errors = []
        slot = SLOTS.get(self.slot)
        if slot is None:
            errors.append(f"구성표에 없는 slot '{self.slot}'")
        elif (self.subtype, self.difficulty) != (slot.subtype, slot.difficulty):
            errors.append(f"유형·난이도 {self.subtype}/{self.difficulty} 가 슬롯 정의 "
                          f"{slot.subtype}/{slot.difficulty} 와 다름")
        if self.difficulty not in DIFFICULTY_LABELS:
            errors.append(f"difficulty {self.difficulty} 는 1~3 이어야 함")
        if not 0 < self.expected_p < 1:
            errors.append(f"expected_p {self.expected_p} 는 0~1 사이여야 함")
        if not self.id.startswith(self.slot):
            errors.append(f"id '{self.id}' 가 slot '{self.slot}' 으로 시작하지 않음")
        if self.format is ItemFormat.MCQ:
            if len(self.choices) != 4:
                errors.append(f"보기 {len(self.choices)}개 (4개 필요)")
            if not isinstance(self.answer, int) or not 0 <= self.answer < len(self.choices):
                errors.append(f"answer {self.answer!r} 가 보기 인덱스 범위 밖")
            if len({str(c) for c in self.choices}) != len(self.choices):
                errors.append("중복된 보기가 있음")
            if "verify" in self.params:
                errors.extend(self._verify_numeric())
        elif self.format is ItemFormat.DIGIT_SPAN:
            if self.params.get("mode") not in ("forward", "backward", "sorting"):
                errors.append("digit_span mode는 forward/backward/sorting")
            if not 3 <= self.params.get("length", 0) <= 9:
                errors.append("digit_span length는 3~9")
        elif self.format is ItemFormat.SPATIAL_SPAN:
            grid = self.params.get("grid", 0)
            if not 3 <= grid <= 5 or not 3 <= self.params.get("length", 0) <= grid * grid:
                errors.append("spatial_span grid 3~5, length 3~grid²")
        elif self.format is ItemFormat.SYMBOL_CODING:
            if self.params.get("duration_sec", 0) <= 0:
                errors.append("symbol_coding duration_sec 필요")
        return errors

    def _verify_numeric(self) -> list[str]:
        """params.verify 식의 값이 정답 보기와 같고 다른 보기와는 다른지 확인."""
        import math

        expected = eval(self.params["verify"], {"math": math})  # 저장소 내부 문항 파일 전용
        nums = [float(str(c).replace(",", "")) for c in self.choices]
        hits = [i for i, n in enumerate(nums) if math.isclose(n, expected)]
        if hits != [self.answer]:
            return [f"verify={expected} 와 일치하는 보기 {hits}, answer={self.answer}"]
        return []
