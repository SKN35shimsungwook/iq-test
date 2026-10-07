import hmac

import streamlit as st

from core import db
from core.runtime import get_engine


def _admin_password() -> str | None:
    try:
        return st.secrets.get("admin_password")
    except Exception:
        return None


expected = _admin_password()
if not expected:
    st.info("`.streamlit/secrets.toml`에 `admin_password`를 설정하면 분석 페이지가 열립니다.", icon=":material/lock:")
    st.stop()

if not st.session_state.get("admin_ok"):
    with st.form("admin_login"):
        pw = st.text_input("관리자 비밀번호", type="password")
        if st.form_submit_button("확인"):
            if hmac.compare_digest(pw, expected):
                st.session_state.admin_ok = True
                st.rerun()
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

engine = get_engine()
norms = db.norm_raw_scores(engine)
responses = db.response_matrix(engine)

with st.container(horizontal=True):
    st.metric("완료한 첫 응시", len(norms), border=True)
    st.metric("저장된 응답", len(responses), border=True)

# TODO(5단계): 점수 분포, 문항별 정답률·변별도, Cronbach α, 평균 응답시간
