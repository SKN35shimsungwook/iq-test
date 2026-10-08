import base64
import json
import random
from datetime import date

import streamlit as st

from core import charts, db
from core import components as ui
from core import exam as ex
from core import report as rp
from core import scoring as sc
from core.runtime import APP_VERSION, get_engine, get_items
from core.schema import (BLUEPRINT, DEEP_MAX_ITEMS, DEEP_MIN_ITEMS, DEEP_ROUND, DEEP_TARGET_SE, DIFFICULTY_LABELS,
                         MAX_ROUNDS, MODE_LABELS, Domain, ItemFormat, Mode, round_label)

ss = st.session_state
if ss.phase != "result":
    st.info("검사를 마치면 이곳에서 결과를 볼 수 있습니다.", icon=":material/info:")
    st.stop()


@st.cache_data(ttl=600, max_entries=4)
def load_norm(mode: str) -> sc.Norm:
    return sc.build_norm(db.norm_thetas(get_engine(), mode), sim=sc.load_sim(mode))


exam, mode, seed = ss.exam, Mode(ss.mode), ss.form_seed
items = {it.id: it for it in get_items()}
norm = load_norm(mode.value)

# 이번 차수를 완료로 기록 (규준에는 1차 검증 첫 응시만 쓰인다)
if not ss.get(f"saved-{ss.session_id}"):
    rows = [r for d in exam["domains"] for r in ex.domain_rows(exam, items, Domain(d), seed)]
    per, total = sc.estimate(rows, items)
    db.complete_session(
        get_engine(), ss.session_id,
        raw_scores={d.value: e.raw for d, e in per.items()},
        domain_index={d.value: round(e.index, 1) for d, e in per.items()},
        ltr_index=round(total.index, 1), percentile=round(sc.percentile(total.theta), 1),
        thetas={"total": total.theta, **{d.value: e.theta for d, e in per.items()}},
        focus_lost=exam.get("blurs", 0),
    )
    ss[f"saved-{ss.session_id}"] = True

rounds = rp.load_rounds(db.series_sessions(get_engine(), ss.series_id), items)
all_rows = [r for rd in rounds for r in rd.rows]
# 점수 기준 단계: 합산은 "같은 차수까지 마친 응시자" 기준, 차수별 점수는 한 차수 분량(1차) 기준
final_stage = rp.stage(sum(not rd.deep for rd in rounds), any(rd.deep for rd in rounds))
final = rp.report(all_rows, items, norm, stage=final_stage)
reports = {rd.round: rp.report(rd.rows, items, norm, rd, stage=None if rd.deep else "1") for rd in rounds}


def pct_text(pct: float) -> str:
    """평균 이상이면 '상위', 아래면 '하위'로 읽기 쉽게."""
    def f(p: float) -> str:
        return f"{p:.0f}" if p >= 1 else f"{max(p, 0.1):.1f}"
    return f"상위 {f(100 - pct)}%" if pct >= 50 else f"하위 {f(pct)}%"


def rank_text(pct: float) -> str:
    rank = max(1, round(100 - pct))
    return f"100명 중 약 {rank}번째"


# ---------------------------------------------------------------- 최종 IQ (항상 맨 위)

s = final.total
used = " + ".join(rd.label for rd in rounds)
st.caption(f"{MODE_LABELS[mode]} · {used}{' 합산' if len(rounds) > 1 else ''} · {date.today():%Y.%m.%d}")
st.title("검사 결과")
with st.container(border=True):
    with st.container(horizontal=True):
        st.metric("IQ (LTR Index)", f"{s.index:.0f}", border=False)
        st.metric("정확한 범위 (90%)", f"{s.lo:.0f} ~ {s.hi:.0f}")
        st.metric("전체 응시자 중 위치", pct_text(s.pct))
        st.metric("수준", sc.level(s.index))
    st.markdown(
        f"당신의 IQ는 **약 {s.index:.0f}**입니다. 측정 오차를 고려하면 실제 IQ는 90% 확률로 "
        f"**{s.lo:.0f}~{s.hi:.0f}** 사이에 있으며 (±{s.margin:.0f}점), 같은 검사를 본 사람 {rank_text(s.pct)}에 해당합니다. "
        f"점수는 IQ와 같은 척도(평균 100, 표준편차 15)입니다."
    )
    if norm.empirical:
        basis = f"이 검사를 처음 응시한 {norm.n:,}명의 실제 분포"
    elif norm.simulated:
        basis = (f"같은 단계까지 푼 가상 응시자 {norm.sim.n:,}명의 시뮬레이션 분포 (문항 난이도 가정 기반 · "
                 f"실제 응시자가 {sc.MIN_NORM_N}명을 넘으면 실제 분포로 바뀝니다. 현재 {norm.n}명)")
    else:
        basis = f"문항 난이도로 만든 가정 기준 (실제 응시자가 {sc.MIN_NORM_N}명을 넘으면 실제 분포로 바뀝니다. 현재 {norm.n}명)"
    st.caption(f"{len(all_rows)}문항의 응답을 합쳐 계산했습니다 · 점수 기준: {basis}")
    if len(rounds) < MAX_ROUNDS:
        st.caption(f"2·3차 검증과 심층검사를 하면 범위가 더 좁아져 IQ를 더 정확하게 알 수 있습니다 (지금 ±{s.margin:.0f}점).")


# ---------------------------------------------------------------- 공통 표시 함수

LETTERS = "ABCD"


def _img(svg: str, width: int) -> None:
    b64 = base64.b64encode(svg.encode()).decode()
    st.html(f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:{width}px;border-radius:6px">')


def _choice(item, idx: int | None) -> str:
    if idx is None:
        return "미응답"
    c = item.choices[idx]
    return LETTERS[idx] if str(c).startswith("<svg") else f"{LETTERS[idx]}. {c}"


def domain_section(rep: rp.RoundReport, quick_note: bool) -> None:
    if quick_note:
        st.caption("빠른 검사는 영역마다 문항이 적어 영역 점수의 오차가 큽니다. 범위를 함께 보세요.")
    rows = [{"영역": d.label, "지수": d.score.index, "하한": d.score.lo, "상한": d.score.hi} for d in rep.domains]
    st.altair_chart(charts.profile_chart(rows))
    st.dataframe({
        "영역": [d.label for d in rep.domains],
        "맞힌 문항": [f"{d.correct} / {d.n}" if d.domain is not Domain.GS else f"{d.raw:g}점" for d in rep.domains],
        "지수": [round(d.score.index) for d in rep.domains],
        "90% 범위": [f"{d.score.lo:.0f}–{d.score.hi:.0f}" for d in rep.domains],
        "평균 풀이 시간": [f"{d.avg_sec:.0f}초" if d.avg_sec else "–" for d in rep.domains],
        "측정 능력": [sc.ABILITY_TEXT[d.domain] for d in rep.domains],
    }, hide_index=True)


def strengths_section(rep: rp.RoundReport) -> None:
    strong, weak = sc.strengths_weaknesses({d.domain: (d.score.index, d.score.margin / sc.CI_Z) for d in rep.domains})
    with st.container(horizontal=True):
        with st.container(border=True):
            st.markdown("**상대적 강점**")
            if strong:
                for d, gap in strong:
                    st.markdown(f":material/trending_up: **{BLUEPRINT[d].label}** — {sc.ABILITY_TEXT[d]}이 "
                                f"다른 영역 평균보다 {gap:.0f}점 높습니다.")
            else:
                st.markdown("뚜렷하게 앞서는 영역 없이 고르게 나타났습니다.")
        with st.container(border=True):
            st.markdown("**상대적 약점**")
            if weak:
                for d, gap in weak:
                    st.markdown(f":material/trending_down: **{BLUEPRINT[d].label}** — {sc.ABILITY_TEXT[d]}이 "
                                f"다른 영역 평균보다 {-gap:.0f}점 낮습니다.")
            else:
                st.markdown("뚜렷하게 처지는 영역이 없습니다.")


def answers_section(rd: rp.RoundData) -> None:
    for d in [Domain(x) for x in rd.progress["domains"]]:
        drows = [r for r in rd.rows if r["domain"] == d.value]
        right = sum(1 for r in drows if r["correct"])
        title = f"{BLUEPRINT[d].label} · {right}/{len(drows)}" if d is not Domain.GS else BLUEPRINT[d].label
        with st.expander(title):
            for k, r in enumerate(drows, 1):
                it = items[r["item_id"]]
                mark = ":green[:material/check_circle:]" if r["correct"] else ":red[:material/cancel:]"
                st.markdown(f"{mark} **{k}.** {it.prompt}".replace("\n", "  \n") +
                            f"  :gray[({DIFFICULTY_LABELS[it.difficulty]})]")
                if it.format is ItemFormat.MCQ:
                    if it.stem_svg:
                        _img(it.stem_svg, 300)
                    mine = int(r["answer"]) if r["answer"] not in (None, "") else None
                    st.markdown(f"내 답: **{_choice(it, mine)}** · 정답: **{_choice(it, it.answer)}**")
                    if str(it.choices[it.answer]).startswith("<svg"):
                        _img(it.choices[it.answer], 110)
                elif it.format is ItemFormat.SYMBOL_CODING:
                    res = json.loads(r["answer"]) if r["answer"] else {"correct": 0, "wrong": 0}
                    st.markdown(f"맞힌 수 **{res['correct']}** · 틀린 수 **{res['wrong']}**")
                else:
                    stim = ex.wm_stimulus(it, rd.seed)
                    shown = stim.get("digits") or " → ".join(str(c + 1) for c in stim["sequence"])
                    expected = stim["expected"] if "digits" in stim else shown
                    given = r["answer"] or "미응답"
                    if "sequence" in stim and r["answer"]:
                        given = " → ".join(str(int(c) + 1) for c in r["answer"].split(","))
                    st.markdown(f"제시: `{shown}` · 내 입력: `{given}` · 정답: `{expected}`")
                if it.explanation:
                    st.caption(it.explanation)
                st.divider()


def round_tab(rd: rp.RoundData, prev: rp.RoundReport | None) -> None:
    rep = reports[rd.round]
    t = rep.total
    title = f"{rd.label} IQ"
    if rd.deep:
        # 심층검사 문항은 1~3차 결과에 맞춰 고른 것이라 그것만으로는 점수를 낼 수 없다 → 1~3차와 합친 정밀 점수를 보여 준다
        cum = rp.cumulative(rounds, items, norm)
        before = next(c for (_, c), x in zip(cum, rounds) if x.round == max(r.round for r in rounds if not r.deep))
        t, title = cum[-1][1], "심층검사 반영 IQ"
        delta = f"{t.index - before.index:+.0f}점 (1~3차 대비)"
    else:
        delta = f"{t.index - prev.total.index:+.0f}점 (앞 차수 대비)" if prev else None
    with st.container(horizontal=True):
        st.metric(title, f"{t.index:.0f}", delta, delta_color="off", border=True)
        st.metric("90% 범위", f"{t.lo:.0f} ~ {t.hi:.0f}", f"±{t.margin:.0f}점", delta_color="off", border=True)
        st.metric("맞힌 문항", f"{rep.correct} / {rep.n}", border=True)
        if rep.minutes is not None:
            st.metric("소요 시간", f"{rep.minutes:.0f}분", border=True)
    if rd.deep:
        st.markdown("**심층검사 분석** · 1~3차 결과에서 출발해 문항을 하나 풀 때마다 영역 점수의 범위가 어떻게 좁혀졌는지 "
                    "보여 줍니다. 맞히면 더 어려운, 틀리면 더 쉬운 문제가 나왔습니다.")
        prior = [r for x in rounds if x.round < DEEP_ROUND for r in x.rows]
        trace = rp.deep_trace(prior, rd.rows, items, norm)
        if trace:
            st.altair_chart(charts.deep_trace_chart(trace))
            done = {row["영역"]: row for row in trace}
            used_n = {BLUEPRINT[Domain(d)].label: len(v) for d, v in rd.progress["items"].items()}
            st.dataframe({
                "영역": list(done),
                "푼 문항": [used_n.get(k, 0) for k in done],
                "최종 지수": [round(v["지수"]) for v in done.values()],
                "최종 90% 범위": [f"{v['하한']:.0f}–{v['상한']:.0f}" for v in done.values()],
                "종료 이유": [("목표 정확도 도달" if (v["상한"] - v["하한"]) / 2 <= sc.CI_Z * 15 * DEEP_TARGET_SE + .5
                              else "최대 문항 도달") for v in done.values()],
            }, hide_index=True)
            st.caption(f"영역마다 오차가 ±{15 * DEEP_TARGET_SE:.0f}점(표준오차 기준) 안쪽이 되거나 {DEEP_MAX_ITEMS}문항에 "
                       f"닿으면 끝났습니다 (최소 {DEEP_MIN_ITEMS}문항).")
    st.markdown("**난이도별 정답률**")
    if rep.by_level:
        st.altair_chart(charts.level_chart(rep.by_level, DIFFICULTY_LABELS))
        st.caption(rp.level_comment(rep.by_level))
    if not rd.deep:
        st.markdown(f"**영역별 결과** ({rd.label}만)")
        domain_section(rep, quick_note=mode is Mode.QUICK)
    notes = []
    if rep.quick_wrong:
        notes.append(f"3초 안에 고른 오답이 {rep.quick_wrong}개 있습니다. 서둘러 찍은 답이 있었다면 점수가 실제보다 낮게 "
                     "나왔을 수 있습니다.")
    if rep.blurs:
        notes.append(f"검사 중 다른 탭이나 창으로 {rep.blurs}번 이동했습니다.")
    for n in notes:
        st.info(n, icon=":material/info:")
    st.markdown("**문항별 정답과 해설**")
    answers_section(rd)


def final_tab() -> None:
    st.markdown("**IQ 분포에서 내 위치**")
    st.altair_chart(charts.distribution_chart(s.index))
    if len(rounds) > 1:
        st.markdown("**차수별 점수와 누적 합산**")
        cum = rp.cumulative(rounds, items, norm)
        points = [{"차수": rd.label, "종류": "차수별", "지수": reports[rd.round].total.index,
                   "하한": reports[rd.round].total.lo, "상한": reports[rd.round].total.hi} for rd in rounds]
        points += [{"차수": rd.label, "종류": "누적 합산", "지수": c.index, "하한": c.lo, "상한": c.hi}
                   for rd, (_, c) in zip(rounds, cum)]
        st.altair_chart(charts.trend_chart(points))
        st.dataframe({
            "합친 차수": [" + ".join(r.label for r in rounds[:k + 1]) for k in range(len(rounds))],
            "IQ": [round(c.index) for _, c in cum],
            "90% 범위": [f"{c.lo:.0f}–{c.hi:.0f}" for _, c in cum],
            "오차": [f"±{c.margin:.0f}점" for _, c in cum],
        }, hide_index=True)
        first, last = cum[0][1], cum[-1][1]
        st.markdown(f"차수를 더할수록 범위가 **±{first.margin:.0f}점 → ±{last.margin:.0f}점**으로 좁아졌습니다.")
        round_only = [reports[rd.round].total.index for rd in rounds if not rd.deep]
        if len(round_only) > 1:
            st.markdown(rp.consistency(round_only, max(reports[rd.round].total.margin for rd in rounds if not rd.deep)))
            gain = round_only[-1] - round_only[0]
            if abs(gain) >= 3:
                st.caption(f"1차보다 마지막 차수가 {gain:+.0f}점입니다. 문제 유형에 익숙해지는 연습 효과가 일부 섞여 있을 수 "
                           "있어, 전체 응시자와 비교하는 기준(상위 %)은 1차 검증 응시자로만 만듭니다.")
    st.markdown("**영역별 최종 결과** (모든 차수 합산)")
    domain_section(final, quick_note=False)
    strengths_section(final)
    if final.by_level:
        st.markdown("**난이도별 정답률** (모든 차수 합산)")
        st.altair_chart(charts.level_chart(final.by_level, DIFFICULTY_LABELS))
        st.caption(rp.level_comment(final.by_level))
    st.markdown("**IQ 구간 해석**")
    st.dataframe({
        "IQ": [f"{a}–{b}" if b < 160 else f"{a} 이상" for a, b, _, _ in rp.LEVEL_GUIDE],
        "수준": [lv for _, _, lv, _ in rp.LEVEL_GUIDE],
        "인구 비율": [share for _, _, _, share in rp.LEVEL_GUIDE],
        "내 위치": ["◀ 여기" if a <= round(s.index) <= b else "" for a, b, _, _ in rp.LEVEL_GUIDE],
    }, hide_index=True)
    st.markdown("**결과 카드**")
    ui.result_card(s.index, pct_text(s.pct), sc.level(s.index), f"{MODE_LABELS[mode]} · {used}",
                   f"{date.today():%Y.%m.%d}", [{"label": d.label, "index": d.score.index} for d in final.domains])


# ---------------------------------------------------------------- 탭

labels = [rd.label for rd in rounds] + ["최종 결과"]
tabs = st.tabs(labels, default="최종 결과")
prev_rep = None
for tab, rd in zip(tabs, rounds):
    with tab:
        round_tab(rd, prev_rep if not rd.deep else None)
    prev_rep = reports[rd.round]
with tabs[-1]:
    final_tab()

st.warning(
    "본 결과는 온라인 인지능력 테스트의 결과이며, 표준화된 전문 심리검사(지능검사)를 대체하지 않습니다. "
    "컨디션, 응시 환경, 기기에 따라 점수가 달라질 수 있습니다.",
    icon=":material/info:",
)

# ---------------------------------------------------------------- 다음 차수

latest = max((rd.round for rd in rounds), default=ss.round)
if ss.round == latest and ss.round < DEEP_ROUND:
    nxt = ss.round + 1
    with st.container(border=True):
        if nxt <= MAX_ROUNDS:
            st.markdown(f"**{round_label(nxt)}** · 지금까지 나온 문제와 겹치지 않는 새 문제로 같은 검사를 한 번 더 풉니다 "
                        f"(약 {15 if mode is Mode.QUICK else 35}분). 결과는 모든 차수를 합쳐 다시 계산합니다."
                        + (" 3차까지 마치면 심층검사를 할 수 있습니다." if nxt == MAX_ROUNDS else ""))
            label, icon = f"{round_label(nxt)} 하기", ":material/replay:"
        else:
            st.markdown("**심층검사** · 1~3차 결과로 추정한 실력에 맞춰 문제를 한 문제씩 골라 냅니다. 영역마다 오차가 "
                        f"±{15 * DEEP_TARGET_SE:.0f}점 안쪽이 되면 다음 영역으로 넘어가며 (영역당 {DEEP_MIN_ITEMS}~"
                        f"{DEEP_MAX_ITEMS}문항), 보통 20~30분 걸립니다.")
            label, icon = "심층검사 하기", ":material/my_location:"
        if st.button(label, type="primary", icon=icon):
            new_seed = random.randrange(2**31)
            ss.round = nxt
            ss.form_seed = new_seed
            ss.exam = None
            ss.session_id = db.start_session(get_engine(), ss.client_id, mode.value, new_seed, APP_VERSION,
                                             series_id=ss.series_id, round_no=ss.round)
            ss.phase = "test"
            st.switch_page("app_pages/test.py")

if st.button("처음으로", icon=":material/restart_alt:"):
    for k in ("exam", "session_id", "form_seed", "mode", "series_id"):
        ss[k] = None
    ss.round = 1
    ss.phase = "intro"
    st.query_params.clear()
    st.switch_page("app_pages/home.py")
st.caption("같은 브라우저에서 다시 응시한 결과는 점수 기준(규준) 계산에서 제외됩니다.")
