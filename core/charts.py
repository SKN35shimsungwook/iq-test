"""결과 화면 차트 (Altair / Vega-Lite). 한 가지 색(앱 기본색)만 쓰고, 값은 툴팁과 표로도 제공한다."""

from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd

from core.scoring import NORMAL

PRIMARY = "#4F46E5"
MUTED = "#9ca3af"


def distribution_chart(index: float) -> alt.LayerChart:
    """평균 100·표준편차 15 정규분포 위에 내 위치를 표시한다."""
    xs = np.arange(40, 160.5, 0.5)
    df = pd.DataFrame({"x": xs, "y": [NORMAL.pdf((x - 100) / 15) for x in xs]})
    df["상위"] = [f"{(1 - NORMAL.cdf((x - 100) / 15)) * 100:.1f}%" for x in xs]
    df["mine"] = df["x"] <= index
    base = alt.Chart(df).encode(
        x=alt.X("x:Q", title="LTR Index (IQ 척도)", scale=alt.Scale(domain=[40, 160]),
                axis=alt.Axis(values=list(range(40, 161, 15)), grid=False)),
        y=alt.Y("y:Q", axis=None, scale=alt.Scale(domain=[0, 0.43])),
    )
    whole = base.mark_area(color=PRIMARY, opacity=0.12, interpolate="monotone")
    below = base.transform_filter("datum.mine").mark_area(color=PRIMARY, opacity=0.45, interpolate="monotone")
    hover = base.mark_rule(color=MUTED, strokeWidth=1, opacity=0).encode(
        tooltip=[alt.Tooltip("x:Q", title="지수"), alt.Tooltip("상위:N", title="상위")],
    ).add_params(alt.selection_point(on="pointerover", nearest=True, fields=["x"], empty=False))
    marks = pd.DataFrame({"x": [100.0, index], "label": ["평균 100", f"나 {index:.0f}"],
                          "dash": [True, False]})
    rule = alt.Chart(marks).mark_rule(strokeWidth=2).encode(
        x="x:Q",
        color=alt.condition("datum.dash", alt.value(MUTED), alt.value(PRIMARY)),
        strokeDash=alt.condition("datum.dash", alt.value([4, 4]), alt.value([1, 0])),
    )
    text = alt.Chart(marks).mark_text(dy=-6, fontWeight="bold", baseline="bottom").encode(
        x="x:Q", y=alt.value(12), text="label:N",
        color=alt.condition("datum.dash", alt.value("#6b7280"), alt.value(PRIMARY)),
    )
    return (whole + below + hover + rule + text).properties(height=220).configure_view(stroke=None)


def profile_chart(rows: list[dict]) -> alt.LayerChart:
    """영역별 지수와 90% 신뢰구간. rows: 영역, 지수, 하한, 상한."""
    df = pd.DataFrame(rows)
    order = list(df["영역"])
    y = alt.Y("영역:N", sort=order, title=None, axis=alt.Axis(labelFontSize=13, ticks=False, domain=False))
    x_scale = alt.Scale(domain=[50, 150])
    tooltip = [alt.Tooltip("영역:N"), alt.Tooltip("지수:Q", format=".0f"),
               alt.Tooltip("범위:N", title="90% 범위")]
    df["범위"] = df["하한"].round().astype(int).astype(str) + "–" + df["상한"].round().astype(int).astype(str)
    base = alt.Chart(df)
    band = base.mark_rule(strokeWidth=6, color=PRIMARY, opacity=0.25, strokeCap="round").encode(
        y=y, x=alt.X("하한:Q", scale=x_scale, title="영역 지수 (평균 100)",
                     axis=alt.Axis(values=list(range(55, 146, 15)))),
        x2="상한:Q", tooltip=tooltip)
    dot = base.mark_point(filled=True, size=140, color=PRIMARY, stroke="white", strokeWidth=2).encode(
        y=y, x=alt.X("지수:Q", scale=x_scale), tooltip=tooltip)
    label = base.mark_text(dx=14, align="left", fontWeight="bold", color="#374151").encode(
        y=y, x=alt.X("지수:Q", scale=x_scale), text=alt.Text("지수:Q", format=".0f"))
    mean = alt.Chart(pd.DataFrame({"x": [100]})).mark_rule(color=MUTED, strokeDash=[4, 4]).encode(x="x:Q")
    return (mean + band + dot + label).properties(height=44 * len(df) + 30).configure_view(stroke=None)
