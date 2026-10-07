import streamlit as st

if st.session_state.phase != "result":
    st.info("검사를 마치면 이곳에서 결과를 볼 수 있습니다.", icon=":material/info:")
    st.stop()

# TODO(4단계): LTR Index·IQ 환산치, 분포 곡선, 영역 레이더, 강점·약점, 해설, 결과 카드
