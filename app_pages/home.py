import random

import streamlit as st

from core import db
from core.components import client_id
from core.runtime import APP_VERSION, get_engine
from core.schema import BLUEPRINT, MODE_LABELS, Domain, Mode


def fmt_time(sec: int) -> str:
    if not sec:
        return "문항별"
    return f"{sec // 60}분" if sec % 60 == 0 else f"{sec // 60}분 {sec % 60}초" if sec > 60 else f"{sec}초"


st.title("종합사고지수 (LTR Index)")
st.caption("언어 · 사고 · 추론 능력을 종합적으로 측정하는 온라인 인지능력 테스트")

mode = st.segmented_control(
    "검사 방식",
    options=list(Mode),
    format_func=MODE_LABELS.get,
    default=Mode.FULL,
    key="mode_choice",
)
mode = mode or Mode.FULL

with st.container(border=True):
    if mode is Mode.QUICK:
        st.markdown("**빠른 검사** · 약 15분 · 종합지수 중심 (영역별 점수는 참고용)")
    else:
        st.markdown("**정밀 검사** · 약 35분 · 영역별 강점·약점 분석 포함")
    rows = [(d, spec.label, spec.length_for(mode), spec.time_for(mode)) for d, spec in BLUEPRINT.items()]
    rows = [(d, label, n, t) for d, label, n, t in rows if n]
    st.table(
        {
            "영역": [label for _, label, _, _ in rows],
            "문항": ["1블록" if d is Domain.GS else f"{n}문항" for d, _, n, _ in rows],
            "제한시간": [fmt_time(t) for _, _, _, t in rows],
        }
    )
    st.caption("조용한 곳에서 한 번에 응시해 주세요.")

st.warning(
    "본 결과는 온라인 인지능력 테스트의 결과이며, 표준화된 전문 심리검사(지능검사)를 대체하지 않습니다.",
    icon=":material/info:",
)

with st.container(border=True):
    st.markdown("**응답 데이터 활용 안내**")
    st.markdown(
        "- 이름·연락처 등 개인을 식별할 수 있는 정보는 수집하지 않습니다.\n"
        "- 문항별 응답과 응답 시간은 익명으로 저장되어 문항 품질 개선과 점수 기준(규준) 계산에만 사용됩니다.\n"
        "- 동의하지 않으면 검사를 진행할 수 없습니다."
    )
    agreed = st.checkbox("위 내용에 동의합니다", value=False, key="consent")

cid = client_id(st.session_state.client_id)
if cid:
    st.session_state.client_id = cid  # 같은 브라우저 재응시를 규준에서 빼기 위한 익명 ID

if st.button("검사 시작", type="primary", disabled=not agreed, icon=":material/play_arrow:"):
    seed = random.randrange(2**31)
    st.session_state.mode = mode
    st.session_state.form_seed = seed
    st.session_state.exam = None
    st.session_state.session_id = db.start_session(
        get_engine(), st.session_state.client_id, mode.value, seed, APP_VERSION
    )
    st.session_state.series_id = st.session_state.session_id
    st.session_state.round = 1
    st.session_state.phase = "test"
    st.switch_page("app_pages/test.py")
