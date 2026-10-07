import base64
import json
from datetime import date

import streamlit as st

from core import charts, db
from core import components as ui
from core import exam as ex
from core import scoring as sc
from core.runtime import get_engine, get_items
from core.schema import BLUEPRINT, DIFFICULTY_LABELS, MODE_LABELS, Domain, ItemFormat, Mode

ss = st.session_state
if ss.phase != "result":
    st.info("검사를 마치면 이곳에서 결과를 볼 수 있습니다.", icon=":material/info:")
    st.stop()


@st.cache_data(ttl=600, max_entries=4)
def load_norm(mode: str) -> sc.Norm:
    return sc.build_norm(db.norm_thetas(get_engine(), mode))


exam, mode, seed = ss.exam, Mode(ss.mode), ss.form_seed
items = {it.id: it for it in get_items()}
domains = [Domain(d) for d in exam["domains"]]
rows = [r for d in domains for r in ex.domain_rows(exam, items, d, seed)]
per, total = sc.estimate(rows, items)
norm = load_norm(mode.value)

z = norm.z(total.theta)
index = sc.to_index(z)
pct = sc.percentile(z)
se_points = 15 * total.se / norm.sd
dom = {}
for d, est in per.items():
    dz = norm.z(est.theta, d)
    dsd = (norm.domain or {}).get(d.value, (0, 1))[1] if norm.empirical else 1.0
    dom[d] = {"index": sc.to_index(dz), "se": 15 * est.se / dsd, "raw": est.raw, "n": est.n_items}

if not ss.get(f"saved-{ss.session_id}"):
    db.complete_session(
        get_engine(), ss.session_id,
        raw_scores={d.value: v["raw"] for d, v in dom.items()},
        domain_index={d.value: round(sc.to_index(per[d].theta), 1) for d in per},
        ltr_index=round(sc.to_index(total.theta), 1), percentile=round(sc.percentile(total.theta), 1),
        thetas={"total": total.theta, **{d.value: e.theta for d, e in per.items()}},
        focus_lost=exam.get("blurs", 0),
    )
    ss[f"saved-{ss.session_id}"] = True

# ---------------------------------------------------------------- 종합 점수

def _pct_text(p: float) -> str:
    return f"{p:.0f}" if p >= 1 else f"{max(p, 0.1):.1f}"


# 평균 이상이면 '상위', 아래면 '하위'로 읽기 쉽게
position = f"상위 {_pct_text(100 - pct)}%" if pct >= 50 else f"하위 {_pct_text(pct)}%"
st.caption(f"{MODE_LABELS[mode]} · {date.today():%Y.%m.%d}")
st.title("검사 결과")
with st.container(border=True):
    with st.container(horizontal=True):
        st.metric("종합사고지수 (LTR Index)", f"{index:.0f}")
        st.metric("전체 응시자 중 위치", position)
        st.metric("수준", sc.level(index))
    lo, hi = max(index - sc.CI_Z * se_points, 40), min(index + sc.CI_Z * se_points, 160)
    st.markdown(
        f"측정 오차를 고려하면 실제 점수는 **{lo:.0f}~{hi:.0f}** 사이일 가능성이 높습니다 (90% 신뢰구간). "
        f"LTR Index는 IQ와 같은 척도(평균 100, 표준편차 15)로 환산한 값이라, "
        f"**IQ 척도로는 약 {index:.0f}**에 해당합니다."
    )
    st.altair_chart(charts.distribution_chart(index))
    if norm.empirical:
        st.caption(f"점수 기준: 이 검사를 처음 응시한 {norm.n:,}명의 실제 분포")
    else:
        st.caption(f"점수 기준: 문항 난이도로 만든 가정 기준 (실제 응시자가 {sc.MIN_NORM_N}명을 넘으면 실제 분포로 바뀝니다. "
                   f"현재 {norm.n}명)")

# ---------------------------------------------------------------- 영역 분석

st.subheader("영역별 결과")
if mode is Mode.QUICK:
    st.caption("빠른 검사는 영역마다 4문항이라 영역 점수의 오차가 큽니다. 영역 분석은 참고용으로만 보세요.")
order = [d for d in sc.DOMAIN_ORDER if d in dom]
profile_rows = [{"영역": BLUEPRINT[d].label, "지수": dom[d]["index"],
                 "하한": max(dom[d]["index"] - sc.CI_Z * dom[d]["se"], 40),
                 "상한": min(dom[d]["index"] + sc.CI_Z * dom[d]["se"], 160)} for d in order]
st.altair_chart(charts.profile_chart(profile_rows))

strong, weak = sc.strengths_weaknesses({d: (dom[d]["index"], dom[d]["se"]) for d in order})
with st.container(horizontal=True):
    with st.container(border=True):
        st.markdown("**상대적 강점**")
        if strong:
            for d, gap in strong:
                st.markdown(f":material/trending_up: **{BLUEPRINT[d].label}** — {sc.ABILITY_TEXT[d]}가 "
                            f"다른 영역 평균보다 {gap:.0f}점 높습니다.")
        else:
            st.markdown("뚜렷하게 앞서는 영역 없이 고르게 나타났습니다.")
    with st.container(border=True):
        st.markdown("**상대적 약점**")
        if weak:
            for d, gap in weak:
                st.markdown(f":material/trending_down: **{BLUEPRINT[d].label}** — {sc.ABILITY_TEXT[d]}가 "
                            f"다른 영역 평균보다 {-gap:.0f}점 낮습니다.")
        else:
            st.markdown("뚜렷하게 처지는 영역이 없습니다.")

table = {
    "영역": [BLUEPRINT[d].label for d in order],
    "맞힌 문항": [f"{dom[d]['raw']:g} / {dom[d]['n']}" if d is not Domain.GS else f"{dom[d]['raw']:g}점" for d in order],
    "지수": [round(dom[d]["index"]) for d in order],
    "90% 범위": [f"{r['하한']:.0f}–{r['상한']:.0f}" for r in profile_rows],
    "측정 능력": [sc.ABILITY_TEXT[d] for d in order],
}
st.dataframe(table, hide_index=True)
if Domain.GS in dom:
    st.caption("처리속도 점수는 90초 동안 (맞힌 수 − 틀린 수)입니다.")

# ---------------------------------------------------------------- 결과 카드

st.subheader("결과 카드")
ui.result_card(index, position, sc.level(index), MODE_LABELS[mode], f"{date.today():%Y.%m.%d}",
               [{"label": BLUEPRINT[d].label, "index": dom[d]["index"]} for d in order])

# ---------------------------------------------------------------- 문항별 정답·해설

LETTERS = "ABCD"


def _img(svg: str, width: int) -> None:
    b64 = base64.b64encode(svg.encode()).decode()
    st.html(f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:{width}px;border-radius:6px">')


def _choice(item, idx: int | None) -> str:
    if idx is None:
        return "미응답"
    c = item.choices[idx]
    return LETTERS[idx] if str(c).startswith("<svg") else f"{LETTERS[idx]}. {c}"


st.subheader("문항별 정답과 해설")
st.caption("문항은 응시할 때마다 바뀌므로 다시 응시해도 같은 문제가 나올 가능성은 낮습니다.")
for d in domains:
    drows = [r for r in rows if r["domain"] == d.value]
    right = sum(1 for r in drows if r["correct"])
    with st.expander(f"{BLUEPRINT[d].label} · {right}/{len(drows)}" if d is not Domain.GS
                     else f"{BLUEPRINT[d].label} · {dom[d]['raw']:g}점"):
        for k, r in enumerate(drows, 1):
            it = items[r["item_id"]]
            mark = ":green[:material/check_circle:]" if r["correct"] else ":red[:material/cancel:]"
            st.markdown(f"{mark} **{k}.** {it.prompt}".replace("\n", "  \n") +
                        f"  :gray[({DIFFICULTY_LABELS[it.difficulty]})]")
            if it.format is ItemFormat.MCQ:
                if it.stem_svg:
                    _img(it.stem_svg, 300)
                mine = int(r["answer"]) if r["answer"] is not None else None
                st.markdown(f"내 답: **{_choice(it, mine)}** · 정답: **{_choice(it, it.answer)}**")
                if str(it.choices[it.answer]).startswith("<svg"):
                    _img(it.choices[it.answer], 110)
            elif it.format is ItemFormat.SYMBOL_CODING:
                res = json.loads(r["answer"]) if r["answer"] else {"correct": 0, "wrong": 0}
                st.markdown(f"맞힌 수 **{res['correct']}** · 틀린 수 **{res['wrong']}**")
            else:
                stim = ex.wm_stimulus(it, seed)
                shown = stim.get("digits") or " → ".join(str(c + 1) for c in stim["sequence"])
                expected = stim["expected"] if "digits" in stim else shown
                given = r["answer"] or "미응답"
                if "sequence" in stim and r["answer"]:
                    given = " → ".join(str(int(c) + 1) for c in r["answer"].split(","))
                st.markdown(f"제시: `{shown}` · 내 입력: `{given}` · 정답: `{expected}`")
            if it.explanation:
                st.caption(it.explanation)
            st.divider()

# ---------------------------------------------------------------- 안내

st.warning(
    "본 결과는 온라인 인지능력 테스트의 결과이며, 표준화된 전문 심리검사(지능검사)를 대체하지 않습니다. "
    "컨디션, 응시 환경, 기기에 따라 점수가 달라질 수 있습니다.",
    icon=":material/info:",
)
if exam.get("blurs"):
    st.caption(f"검사 중 다른 탭이나 창으로 {exam['blurs']}번 이동한 기록이 있습니다.")


if st.button("처음으로", icon=":material/restart_alt:"):
    for k in ("exam", "session_id", "form_seed", "mode"):
        ss[k] = None
    ss.phase = "intro"
    st.query_params.clear()
    st.switch_page("app_pages/home.py")
st.caption("같은 브라우저에서 다시 응시한 결과는 점수 기준(규준) 계산에서 제외됩니다.")
