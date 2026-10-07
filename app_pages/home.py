import random

import streamlit as st

from core import db
from core.runtime import APP_VERSION, get_engine
from core.schema import TEST_PLAN

st.title("종합사고지수 (LTR Index)")
st.caption("언어 · 사고 · 추론 능력을 종합적으로 측정하는 온라인 인지능력 테스트")

with st.container(border=True):
    st.markdown("**검사 구성**")
    st.table(
        {
            "영역": [spec.label for spec in TEST_PLAN.values()],
            "문항": [f"{spec.slots}문항" if spec.slots > 1 else "1블록" for spec in TEST_PLAN.values()],
            "제한시간": [
                "문항별" if not spec.time_limit_sec
                else f"{spec.time_limit_sec // 60}분" if spec.time_limit_sec % 60 == 0
                else f"{spec.time_limit_sec}초"
                for spec in TEST_PLAN.values()
            ],
        }
    )
    st.markdown("총 약 **25분** 소요됩니다. 조용한 곳에서 한 번에 응시해 주세요.")

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

if st.button("검사 시작", type="primary", disabled=not agreed, icon=":material/play_arrow:"):
    seed = random.randrange(2**31)
    st.session_state.form_seed = seed
    st.session_state.session_id = db.start_session(
        get_engine(), st.session_state.client_id, seed, APP_VERSION
    )
    st.session_state.phase = "test"
    st.switch_page("app_pages/test.py")
