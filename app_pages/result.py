import streamlit as st

from core.schema import BLUEPRINT, Domain

if st.session_state.phase != "result":
    st.info("검사를 마치면 이곳에서 결과를 볼 수 있습니다.", icon=":material/info:")
    st.stop()

exam = st.session_state.exam

# TODO(4단계): LTR Index·IQ 환산치, 분포 곡선, 영역 레이더, 강점·약점, 해설, 결과 카드
st.subheader("검사 완료")
st.caption("점수 환산과 결과 분석 화면은 다음 단계에서 만듭니다. 지금은 영역별 원점수만 보여 줍니다.")
st.table({
    "영역": [BLUEPRINT[Domain(d)].label for d in exam["domains"]],
    "원점수": [f"{exam['raw'].get(d, 0):g} / {len(exam['items'][d])}" if d != "gs" else f"{exam['raw'].get(d, 0):g}"
             for d in exam["domains"]],
})
if exam["blurs"]:
    st.caption(f"검사 중 다른 탭이나 창으로 {exam['blurs']}번 이동했습니다.")
