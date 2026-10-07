import streamlit as st

from core.item_bank import build_form
from core.runtime import get_items
from core.schema import BLUEPRINT, DIFFICULTY_LABELS, MODE_LABELS

if st.session_state.phase != "test":
    st.info("시작 화면에서 안내에 동의한 뒤 검사를 시작해 주세요.", icon=":material/info:")
    st.page_link("app_pages/home.py", label="시작 화면으로", icon=":material/home:")
    st.stop()

mode = st.session_state.mode
form = build_form(get_items(), st.session_state.form_seed, mode)

# TODO(3단계): 영역별 타이머·문항 응시 화면으로 교체
st.subheader(f"검사지 미리보기 · {MODE_LABELS[mode]}")
for domain, items in form.items():
    spec = BLUEPRINT[domain]
    with st.expander(f"{spec.label} — {len(items)}/{len(spec.slots_for(mode))}문항"):
        for it in items:
            st.markdown(f"`{it.id}` · {it.subtype} · {DIFFICULTY_LABELS[it.difficulty]} · {it.prompt}")
