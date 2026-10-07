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
    DIGIT_SPAN = "digit_span"        # 숫자 순차 제시 후 입력
    SYMBOL_CODING = "symbol_coding"  # 기호→숫자 변환 블록


@dataclass(frozen=True)
class DomainSpec:
    label: str
    slots: int           # 출제 문항 수 (슬롯마다 동형 문항 중 1개 랜덤)
    time_limit_sec: int  # 영역 제한시간, 0이면 문항 자체 타이밍
    weight: float = 1.0  # 종합지수 가중치


# 검사 구성 (영역 순서 = 출제 순서)
TEST_PLAN: dict[Domain, DomainSpec] = {
    Domain.GF: DomainSpec("유동추론", slots=10, time_limit_sec=8 * 60),
    Domain.GC: DomainSpec("언어", slots=7, time_limit_sec=4 * 60),
    Domain.GQ: DomainSpec("수리", slots=6, time_limit_sec=5 * 60),
    Domain.GV: DomainSpec("시공간", slots=5, time_limit_sec=4 * 60),
    Domain.GWM: DomainSpec("작업기억", slots=5, time_limit_sec=0),
    Domain.GS: DomainSpec("처리속도", slots=1, time_limit_sec=90),
}

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
    svg: dict | None = None  # 문제 본문 도형 스펙 (생성기 입력)
    params: dict = field(default_factory=dict)        # 형식별 추가 설정
    explanation: str = ""
    expected_p: float = 0.5  # 예상 정답률 (규준 데이터 전 가정 규준에 사용)
    version: int = 1
    irt_a: float | None = None
    irt_b: float | None = None
    irt_c: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        d = dict(d)
        d["domain"] = Domain(d["domain"])
        d["format"] = ItemFormat(d["format"])
        return cls(**d)

    def validate(self) -> list[str]:
        """문항 자체의 형식 오류 목록 (비어 있으면 통과)."""
        errors = []
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
        return errors
