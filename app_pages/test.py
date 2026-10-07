import base64
import json
import re
import time

import streamlit as st

from core import components as ui
from core import db
from core import exam as ex
from core.item_bank import build_form
from core.runtime import get_engine, get_items, save_progress
from core.schema import (BLUEPRINT, DEEP_MAX_ITEMS, DEEP_MIN_ITEMS, DEEP_ROUND, MODE_LABELS, Domain, ItemFormat,
                         round_label)

INTROS = {
    Domain.GF: "그림 속 규칙을 찾아 빈칸이나 다음에 올 그림을 고르는 문제입니다.",
    Domain.GC: "낱말의 뜻과 관계를 묻는 문제입니다.",
    Domain.GQ: "수의 규칙을 찾거나 간단한 계산으로 답을 구하는 문제입니다. 종이와 펜을 써도 됩니다.",
    Domain.GV: "도형을 머릿속으로 돌리고, 접고, 맞춰 보는 문제입니다.",
    Domain.GWM: "화면에 잠깐 나타나는 숫자나 위치를 기억했다가 입력합니다. 한 번만 보여 주며 메모는 하지 마세요. "
                "보여 주는 도중에 새로고침하면 그 문항은 0점 처리됩니다.",
    Domain.GS: "기호를 보고 짝이 되는 숫자를 최대한 빠르고 정확하게 누릅니다. 틀린 만큼 감점됩니다. "
               "본 검사 도중에 새로고침하면 0점 처리됩니다.",
}

if st.session_state.phase != "test":
    st.info("시작 화면에서 안내에 동의한 뒤 검사를 시작해 주세요.", icon=":material/info:")
    st.page_link("app_pages/home.py", label="시작 화면으로", icon=":material/home:")
    st.stop()

ss = st.session_state
mode, seed = ss.mode, ss.form_seed
items = {it.id: it for it in get_items()}


def prior_rounds() -> list[dict]:
    """같은 묶음에서 끝낸 1~3차의 응답 행 (심층검사의 출발점)."""
    rows = []
    for r in db.series_sessions(get_engine(), ss.series_id):
        if r["completed_at"] and r["progress"] and r["round"] < DEEP_ROUND:
            prog = r["progress"]
            rows += [x for d in prog["domains"] for x in ex.domain_rows(prog, items, Domain(d), r["form_seed"])]
    return rows


if ss.get("exam") is None:
    seen = db.seen_items(get_engine(), ss.series_id) if ss.get("round", 1) > 1 else set()
    if ss.round == DEEP_ROUND:
        ss.exam = ex.new_deep_exam(prior_rounds(), seen, mode)
    else:
        ss.exam = ex.new_exam(build_form(list(items.values()), seed, mode, exclude=seen), mode)
exam = ss.exam
deep = exam.get("kind") == "deep"
domain = ex.current_domain(exam)
spec = BLUEPRINT[domain]
ids = exam["items"][domain.value]


def close_domain() -> None:
    """현재 영역을 채점·저장하고 다음 영역(또는 결과)으로 넘어간다."""
    if exam["stage"] == "items" and ids and items[ids[exam["i"]]].format is ItemFormat.MCQ:
        ex.track_time(exam, ids[exam["i"]])
    rows = ex.domain_rows(exam, items, domain, seed)
    db.save_responses(get_engine(), ss.session_id, rows)
    finished = ex.finish_domain(exam, rows)
    save_progress()
    if finished:
        ss.phase = "result"
        st.switch_page("app_pages/result.py")
    st.rerun()


def advance() -> None:
    """현재 문항을 마치고 다음 문항으로. 더 낼 문항이 없으면 영역을 닫는다."""
    if deep:
        if ex.deep_next(exam, items, seed) is None:
            close_domain()
    elif exam["i"] >= len(ids) - 1:
        close_domain()
    exam["i"] += 1
    exam["entered"] = time.time()
    save_progress()
    st.rerun()


def go_to(i: int) -> None:
    ex.track_time(exam, ids[exam["i"]])
    exam["i"] = i
    save_progress()


# ---------------------------------------------------------------- 영역 안내

step = f"{exam['d'] + 1}/{len(exam['domains'])}"
if exam["stage"] == "intro":
    st.caption(f"{MODE_LABELS[mode]} · {round_label(ss.round)} · 영역 {step}")
    st.subheader(spec.label)
    limit = ex.domain_time_limit(domain, mode, deep)
    with st.container(border=True):
        st.markdown(INTROS[domain])
        if deep:
            facts = ["지금까지의 결과에 맞춰 **한 문제씩** 고릅니다",
                     f"정확도가 충분해지면 다음 영역으로 (**{DEEP_MIN_ITEMS}~{DEEP_MAX_ITEMS}문항**)",
                     "답을 확인하면 앞 문제로 돌아갈 수 없습니다"]
        else:
            facts = [f"**{spec.length_for(mode)}문항**" if domain is not Domain.GS else "**1블록**",
                     "쉬운 문제부터 어려운 문제 순서입니다" if domain is not Domain.GS else "연습 3회 후 **90초**"]
        if limit:
            facts.append(f"제한시간 **{limit // 60}분{f' {limit % 60}초' if limit % 60 else ''}**")
            facts.append("시간이 끝나면 자동으로 다음 영역으로 넘어갑니다")
        elif domain is Domain.GWM:
            facts.append("문항마다 한 번씩 보여 줍니다")
        st.markdown(" · ".join(facts))
    if st.button("시작", type="primary", icon=":material/play_arrow:"):
        ex.start_domain(exam, mode)
        if deep and ex.deep_next(exam, items, seed) is None:
            close_domain()
        save_progress()
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- 문항

if ex.is_expired(exam):
    st.toast(f"{spec.label} 영역 시간이 끝났습니다.", icon=":material/timer_off:")
    close_domain()

item = items[ids[exam["i"]]]
if notice := ss.pop("notice", None):
    st.toast(notice, icon=":material/warning:")
with st.container(horizontal=True, vertical_alignment="center"):
    progress = f"{exam['i'] + 1}번째 문항" if deep else f"{exam['i'] + 1} / {spec.length_for(mode)}"
    st.markdown(f"**{spec.label}** · {progress}")
    if exam["deadline"]:
        remaining = int((exam["deadline"] - time.time()) * 1000)
        total = ex.domain_time_limit(domain, mode, deep) * 1000
        expired, blurs = ui.countdown(f"{ss.round}-{exam['d']}", remaining, total, exam["blurs"], key="countdown")
        exam["blurs"] = blurs or exam["blurs"]
        if expired:
            st.rerun()

if item.format is ItemFormat.MCQ:
    st.markdown(f"#### {item.prompt}".replace("\n", "  \n"))
    if item.stem_svg:
        m = re.search(r'viewBox="0 0 ([\d.]+)', item.stem_svg)
        width = min(float(m.group(1)) * 1.15, 640) if m else 360
        b64 = base64.b64encode(item.stem_svg.encode()).decode()
        st.html(f'<img src="data:image/svg+xml;base64,{b64}" alt="문제 그림" draggable="false" '
                f'style="display:block;width:100%;max-width:{width:.0f}px;margin:4px auto 12px;border-radius:8px">')
    prev = exam["answers"].get(item.id)
    sel = ui.choice_grid(item.choices, int(prev) if prev is not None else None, key=f"choice-{ss.round}-{item.id}")
    if sel is not None and exam["answers"].get(item.id) != str(sel):
        exam["answers"][item.id] = str(sel)
        save_progress()

    st.space("small")
    if deep:
        # 심층검사: 답에 따라 다음 문제가 정해지므로 한 문제씩 확정하고 앞으로만 간다
        if st.button("확인", type="primary", icon=":material/check:", disabled=item.id not in exam["answers"]):
            ex.track_time(exam, item.id)
            advance()
    else:
        answered = [i for i, x in enumerate(ids) if x in exam["answers"]]
        last = exam["i"] == len(ids) - 1
        with st.container(horizontal=True):
            st.button("이전", icon=":material/arrow_back:", disabled=exam["i"] == 0,
                      on_click=go_to, args=(exam["i"] - 1,))
            if not last:
                st.button("다음", type="primary", icon=":material/arrow_forward:", on_click=go_to,
                          args=(exam["i"] + 1,))
            elif st.button("영역 제출", type="primary", icon=":material/check:"):
                ss.confirm_submit = True

        jump = st.pills(
            "문항 이동", options=list(range(len(ids))), selection_mode="single", default=exam["i"],
            format_func=lambda k: f"{k + 1}{' ✓' if k in answered else ''}",
            key=f"jump-{ss.round}-{exam['d']}-{exam['i']}",
        )
        if jump is not None and jump != exam["i"]:
            go_to(jump)
            st.rerun()

        if ss.get("confirm_submit"):
            missing = len(ids) - len(answered)

            @st.dialog("영역을 제출할까요?")
            def confirm():
                if missing:
                    st.warning(f"답하지 않은 문항이 {missing}개 있습니다. 제출하면 이 영역으로 다시 돌아올 수 없습니다.")
                else:
                    st.write("제출하면 이 영역으로 다시 돌아올 수 없습니다.")
                with st.container(horizontal=True):
                    if st.button("계속 풀기"):
                        ss.confirm_submit = False
                        st.rerun()
                    if st.button("제출", type="primary"):
                        ss.confirm_submit = False
                        close_domain()

            confirm()

else:
    token = f"{ss.session_id}-{item.id}"
    started_ids = exam.setdefault("started", [])
    live_key = f"live-{ss.session_id}-{item.id}"  # 이 브라우저 세션에서 제시를 시작했다는 표시 (새로고침하면 사라짐)
    if item.id in started_ids and item.id not in exam["answers"] and not ss.get(live_key):
        # 제시가 시작된 뒤 새로고침했다 → 같은 자극을 다시 보여 주지 않고 0점 처리
        exam["answers"][item.id] = ex.ABORTED_GS if item.format is ItemFormat.SYMBOL_CODING else ""
        ss.notice = "진행 중에 새로고침해서 앞 문항은 0점 처리되었습니다."
        done = True
    elif item.format is ItemFormat.SYMBOL_CODING:
        stim = ex.gs_stimulus(item, seed)
        done, started = ui.symbol_coding(token, stim["symbols"], stim["sequence"], item.params["duration_sec"])
        if done:
            exam["answers"][item.id] = json.dumps(done)
            exam["ms"][item.id] = item.params["duration_sec"] * 1000
    else:
        stim = ex.wm_stimulus(item, seed)
        p = item.params
        if item.format is ItemFormat.SPATIAL_SPAN:
            done, started = ui.spatial_span(token, p["grid"], stim["sequence"], p["show_ms"], p["gap_ms"])
        else:
            done, started = ui.digit_span(token, stim["digits"], p["mode"], p["show_ms"], p["gap_ms"])
        if done:
            exam["answers"][item.id] = done["answer"]
            exam["ms"][item.id] = done["rt_ms"]
    if not done and started and item.id not in started_ids:
        started_ids.append(item.id)
        ss[live_key] = True
        save_progress()
    if done:
        advance()
