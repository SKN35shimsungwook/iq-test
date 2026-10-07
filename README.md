# 종합사고지수 (LTR Index) 테스트

언어(Language)·사고(Thinking)·추론(Reasoning)을 측정하는 온라인 인지능력 테스트입니다.
결과는 자체 지수(평균 100, 표준편차 15)와 IQ 환산치로 보여주며, 응답을 익명으로 쌓아 문항 분석과 규준 보정에 사용합니다.

> 본 테스트는 표준화된 전문 심리검사(지능검사)를 대체하지 않습니다.

## 검사 구성

| 영역 | 문항 | 제한시간 |
|---|---|---|
| 유동추론 (Gf) | 10 | 8분 |
| 언어 (Gc) | 7 | 4분 |
| 수리 (Gq) | 6 | 5분 |
| 시공간 (Gv) | 5 | 4분 |
| 작업기억 (Gwm) | 5 | 문항별 |
| 처리속도 (Gs) | 1블록 | 90초 |

슬롯마다 동형 문항을 두고 응시마다 무작위로 하나를 출제합니다.

## 실행

```bash
pip install -r requirements-dev.txt
streamlit run streamlit_app.py
```

- 기본 저장소는 `data/iq_test.db`(SQLite)입니다.
- Supabase를 쓰려면 `.streamlit/secrets.toml.example`을 `secrets.toml`로 복사하고 `[connections.sql]`을 채웁니다.

## 구조

```
streamlit_app.py       진입점 (st.navigation)
app_pages/             시작 · 검사 · 결과 · 관리자 분석
core/schema.py         문항 스키마, 영역·문항 수·제한시간 정의
core/item_bank.py      문항 로드·검증·검사지 구성
core/db.py             세션·응답 저장 (SQLite / Postgres 공용)
items/*.json           문항은행
scripts/validate_items.py  문항 검증 (--strict: 슬롯 수까지)
```

## 문항 작성 규칙

- `id`는 `<slot><동형 문자>` 형식 (예: `gf-03b`), 슬롯 번호 순서가 출제 순서이므로 쉬운 문항부터 번호를 매깁니다.
- `answer`는 보기 인덱스(0~3), `expected_p`는 예상 정답률(규준 데이터가 쌓이기 전 가정 규준에 사용).
- 문항을 고치면 `version`을 올립니다. 응답 로그에 버전이 함께 저장됩니다.
