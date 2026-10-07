import streamlit as st

from core.runtime import init_state

st.set_page_config(page_title="종합사고지수 테스트", page_icon=":material/psychology:", layout="centered")

init_state()

page = st.navigation(
    {
        "": [
            st.Page("app_pages/home.py", title="시작", icon=":material/home:", default=True),
            st.Page("app_pages/test.py", title="검사", icon=":material/edit_note:"),
            st.Page("app_pages/result.py", title="결과", icon=":material/insights:"),
        ],
        "관리": [
            st.Page("app_pages/admin.py", title="분석", icon=":material/admin_panel_settings:"),
        ],
    },
    position="top",
)

page.run()
