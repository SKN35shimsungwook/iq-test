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
MIN_FORMS = 6       # 4지선다 슬롯당 최소 동형 문항 수 (추가 라운드 3회까지 겹치지 않게)
MAX_ROUNDS = 3      # 결과 후 '다른 문제로 한 번 더' 포함 최대 라운드
MAX_SAME_TYPE = 2   # 한 검사지·한 영역 안에서 같은 유형 최대 출제 수
MIN_DOMAIN_POOL = 30  # 4지선다 영역당 최소 문항 풀 크기
PANELS = ("easy", "mid", "hard")


@dataclass(frozen=True)
class SlotSpec:
    id: str          # "영역-유형-난이도", 예: "gf-matrix-3"
    subtype: str     # 문항 유형
    difficulty: int  # 1~4


@dataclass(frozen=True)
class Plan:
    """2단계 적응형 출제: 1단계를 풀고 정답률에 따라 쉬운/중간/어려운 묶음 중 하나로 이어진다."""
    stage1: tuple[str, ...]
    panels: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def paths(self) -> dict[str, tuple[str, ...]]:
        return {p: self.stage1 + slots for p, slots in self.panels.items()} or {"": self.stage1}


@dataclass(frozen=True)
class DomainSpec:
    label: str
    full: Plan
    quick: Plan | None
    time_full: int     # 영역 제한시간(초), 0이면 문항 자체 타이밍
    time_quick: int = 0

    def plan_for(self, mode: Mode) -> Plan | None:
        return self.full if mode is Mode.FULL else self.quick

    def length_for(self, mode: Mode) -> int:
        plan = self.plan_for(mode)
        return len(next(iter(plan.paths().values()))) if plan else 0

    def time_for(self, mode: Mode) -> int:
        return self.time_full if mode is Mode.FULL else self.time_quick

    @property
    def slot_ids(self) -> list[str]:
        ids = []
        for plan in (self.full, self.quick):
            for path in (plan.paths().values() if plan else []):
                ids += [x for x in path if x not in ids]
        return ids


def _plan(d: str, stage1: str, easy: str = "", mid: str = "", hard: str = "") -> Plan:
    """"matrix2 sequence2" 같은 짧은 표기를 슬롯 ID로 바꾼다."""
    def ids(text: str) -> tuple[str, ...]:
        return tuple(f"{d}-{tok[:-1]}-{tok[-1]}" for tok in text.split())
    panels = {k: ids(v) for k, v in (("easy", easy), ("mid", mid), ("hard", hard)) if v}
    return Plan(ids(stage1), panels)


# 검사 구성표 (영역 순서 = 출제 순서). 영역 경계:
#   유동추론 = 도형만, 수리 = 숫자만, 언어 = 어휘·지식 기반, 시공간 = 공간 조작
# 같은 경로(1단계 + 묶음) 안에서 같은 유형은 최대 2번, 빠른 검사는 4문항이 모두 다른 유형.
BLUEPRINT: dict[Domain, DomainSpec] = {
    Domain.GF: DomainSpec(
        "유동추론",
        full=_plan("gf", "matrix2 sequence2 analogy2 odd_one_out2 transform2",
                   easy="matrix1 sequence1 odd_one_out1 analogy1 transform1",
                   mid="matrix3 sequence3 odd_one_out3 analogy3 transform3",
                   hard="matrix4 sequence4 odd_one_out3 analogy4 transform4"),
        quick=_plan("gf", "matrix2 odd_one_out3", easy="sequence1 transform1",
                    mid="sequence3 transform3", hard="sequence4 transform4"),
        time_full=9 * 60, time_quick=4 * 60),
    Domain.GC: DomainSpec(
        "언어",
        full=_plan("gc", "synonym2 analogy2 category2 completion2",
                   easy="synonym1 analogy1 category1 antonym2",
                   mid="synonym3 analogy3 category3 completion3",
                   hard="synonym4 analogy4 antonym3 completion4"),
        quick=_plan("gc", "synonym2 category3", easy="analogy1 antonym2",
                    mid="analogy3 completion3", hard="analogy4 completion4"),
        time_full=5 * 60, time_quick=150),
    Domain.GQ: DomainSpec(
        "수리",
        full=_plan("gq", "series2 number_matrix2 operator2 applied2",
                   easy="series1 applied1 data1 operator1",
                   mid="series3 number_matrix3 data2 applied3",
                   hard="series4 number_matrix4 operator3 applied4"),
        quick=_plan("gq", "series2 number_matrix3", easy="operator1 applied1",
                    mid="operator2 applied3", hard="operator3 applied4"),
        time_full=7 * 60, time_quick=4 * 60),
    Domain.GV: DomainSpec(
        "시공간",
        full=_plan("gv", "rotation2 paper_fold2 cube_net2 assembly2",
                   easy="rotation1 paper_fold1 cube_net1 assembly1",
                   mid="rotation3 paper_fold3 cube_net3 assembly3",
                   hard="rotation4 paper_fold4 cube_net4 assembly4"),
        quick=_plan("gv", "rotation2 cube_net3", easy="paper_fold1 assembly1",
                    mid="paper_fold3 assembly3", hard="paper_fold4 assembly4"),
        time_full=7 * 60, time_quick=4 * 60),
    Domain.GWM: DomainSpec(
        "작업기억",
        full=_plan("gwm", "forward2 backward2 sorting2 spatial2",
                   easy="forward1 backward1 sorting1 spatial1",
                   mid="forward3 backward3 sorting3 spatial3",
                   hard="forward4 backward4 sorting4 spatial4"),
        quick=_plan("gwm", "forward2 spatial3", easy="backward1 sorting1",
                    mid="backward3 sorting3", hard="backward4 sorting4"),
        time_full=0),
    Domain.GS: DomainSpec("처리속도", full=_plan("gs", "symbol_coding2"), quick=None, time_full=90),
}


def _slot(slot_id: str) -> SlotSpec:
    _, subtype, level = slot_id.rsplit("-", 2)
    return SlotSpec(slot_id, subtype, int(level))


SLOTS: dict[str, SlotSpec] = {i: _slot(i) for spec in BLUEPRINT.values() for i in spec.slot_ids}

DIFFICULTY_LABELS = {1: "쉬움", 2: "보통", 3: "어려움", 4: "매우 어려움"}
EXPECTED_P = {1: 0.85, 2: 0.65, 3: 0.45, 4: 0.25}  # 난이도별 기본 예상 정답률


@dataclass
class Item:
    id: str                  # 예: "gf-01a" (슬롯 gf-01의 동형 a)
    domain: Domain
    slot: str                # 동형 문항끼리 공유하는 슬롯 ID
    format: ItemFormat
    subtype: str             # 예: matrix, vocabulary, series, rotation
    difficulty: int          # 1~4
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
            errors.append(f"difficulty {self.difficulty} 는 1~4 이어야 함")
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
