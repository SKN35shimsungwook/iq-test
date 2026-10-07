"""응시 화면용 인라인 커스텀 컴포넌트 (Streamlit Custom Components v2).

- client_id: 브라우저 localStorage에 익명 ID를 만들어 재응시를 판별
- countdown: 영역 제한시간 표시 + 만료 알림 + 탭 이탈 횟수 집계
- choice_grid: 4지선다 보기 타일 (SVG/텍스트), 1~4·A~D 키 지원
- digit_span: 숫자 순차 제시 후 키패드 입력 (정순·역순·정렬)
- spatial_span: 격자 칸 순차 점등 후 같은 순서로 누르기
- symbol_coding: 기호→숫자 변환 (연습 3회 + 제한시간 본 검사)

각 컴포넌트는 data.token이 같으면 화면을 다시 만들지 않아, 재실행돼도 진행 중인 애니메이션이 끊기지 않는다.
"""

from __future__ import annotations

import html as html_lib

import streamlit as st

BASE_CSS = """
:host { --pri: var(--st-primary-color, #4F46E5); --txt: var(--st-text-color, #111827);
        --bg2: var(--st-secondary-background-color, #f3f4f6); --bd: var(--st-border-color, #d1d5db);
        font-family: var(--st-font, sans-serif); color: var(--txt); }
* { box-sizing: border-box; user-select: none; -webkit-user-select: none; }
button { font: inherit; cursor: pointer; }
.btn { border: 1px solid var(--bd); background: var(--bg2); color: var(--txt); border-radius: 8px;
       padding: 10px 18px; font-size: 16px; }
.btn.pri { background: var(--pri); border-color: var(--pri); color: #fff; font-weight: 600; }
.btn:disabled { opacity: .4; cursor: default; }
.center { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 8px 0; }
.hint { font-size: 14px; opacity: .75; text-align: center; }
"""

# ---------------------------------------------------------------- 익명 브라우저 ID

_CLIENT_ID = st.components.v2.component(
    "ltr_client_id",
    html="<span></span>",
    js="""
export default function (component) {
  const { data, setStateValue } = component
  let id = null
  try {
    id = localStorage.getItem("ltr_cid")
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem("ltr_cid", id)
    }
  } catch (e) {
    return
  }
  if (data.cid !== id) setStateValue("cid", id)
}
""",
)


def client_id(current: str | None) -> str | None:
    """localStorage의 익명 ID. 저장소를 쓸 수 없으면 None."""
    result = _CLIENT_ID(key="ltr_cid", data={"cid": current}, default={"cid": None},
                        on_cid_change=lambda: None)
    return result.cid


# ---------------------------------------------------------------- 남은 시간

_COUNTDOWN = st.components.v2.component(
    "ltr_countdown",
    html="<div class='cd'><span class='t'></span><div class='bar'><div class='fill'></div></div></div>",
    css=BASE_CSS + """
.cd { display: flex; align-items: center; gap: 10px; min-width: 200px; }
.t { font-variant-numeric: tabular-nums; font-weight: 700; font-size: 18px; min-width: 56px; }
.bar { flex: 1; height: 8px; background: var(--bg2); border-radius: 4px; overflow: hidden; }
.fill { height: 100%; background: var(--pri); transition: width .25s linear; }
.low .t { color: #dc2626; } .low .fill { background: #dc2626; }
""",
    js="""
export default function (component) {
  const { data, parentElement, setTriggerValue, setStateValue } = component
  const s = parentElement.__cd || (parentElement.__cd = { blurs: data.blurs || 0 })
  if (s.token !== data.token) { s.token = data.token; s.firedAt = 0 }
  s.endAt = performance.now() + data.remaining_ms
  s.total = data.total_ms
  const box = parentElement.querySelector(".cd")
  const tick = () => {
    const left = Math.max(0, s.endAt - performance.now())
    const sec = Math.ceil(left / 1000)
    box.querySelector(".t").textContent = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`
    box.querySelector(".fill").style.width = `${(left / s.total) * 100}%`
    box.classList.toggle("low", left < 30000)
    if (left <= 0 && (!s.firedAt || performance.now() - s.firedAt > 3000)) {
      s.firedAt = performance.now()
      setTriggerValue("expired", s.token)
    }
  }
  tick()
  if (!s.timer) s.timer = setInterval(tick, 250)
  if (!s.onVis) {
    s.onVis = () => { if (document.hidden) { s.blurs += 1; setStateValue("blurs", s.blurs) } }
    document.addEventListener("visibilitychange", s.onVis)
  }
  return () => {
    clearInterval(s.timer)
    document.removeEventListener("visibilitychange", s.onVis)
    parentElement.__cd = null
  }
}
""",
)


def countdown(token: str, remaining_ms: int, total_ms: int, blurs: int, key: str):
    """(만료 trigger, 누적 탭 이탈 수)"""
    r = _COUNTDOWN(key=key, data={"token": token, "remaining_ms": remaining_ms, "total_ms": total_ms, "blurs": blurs},
                   default={"blurs": blurs}, on_blurs_change=lambda: None, on_expired_change=lambda: None)
    return r.expired, r.blurs


# ---------------------------------------------------------------- 4지선다 보기

_CHOICES = st.components.v2.component(
    "ltr_choice_grid",
    html="<div class='grid'></div>",
    css=BASE_CSS + """
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.grid.text { grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (max-width: 560px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.tile { position: relative; border: 2px solid var(--bd); background: var(--bg2); color: var(--txt);
        border-radius: 10px; padding: 26px 10px 10px; min-height: 64px; text-align: left; }
.tile:hover { border-color: var(--pri); }
.tile.on { border-color: var(--pri); box-shadow: 0 0 0 3px color-mix(in srgb, var(--pri) 25%, transparent); }
.lab { position: absolute; top: 6px; left: 10px; font-size: 13px; font-weight: 700; opacity: .6; }
.tile.on .lab { color: var(--pri); opacity: 1; }
.body { font-size: 17px; line-height: 1.4; }
.body svg { width: 100%; height: auto; display: block; max-width: 150px; margin: 0 auto; border-radius: 6px; }
""",
    js="""
export default function (component) {
  const { data, parentElement, setStateValue } = component
  const grid = parentElement.querySelector(".grid")
  if (grid.dataset.token !== data.token) {
    grid.dataset.token = data.token
    grid.className = data.svg ? "grid" : "grid text"
    grid.innerHTML = ""
    data.choices.forEach((content, i) => {
      const b = document.createElement("button")
      b.type = "button"
      b.className = "tile"
      b.dataset.i = i
      b.innerHTML = `<span class="lab">${"ABCD"[i]}</span><div class="body">${content}</div>`
      b.onclick = () => pick(i)
      grid.appendChild(b)
    })
  }
  const mark = (sel) => grid.querySelectorAll(".tile").forEach(
    (t) => t.classList.toggle("on", Number(t.dataset.i) === sel))
  const pick = (i) => { mark(i); setStateValue("selected", i) }
  mark(data.selected ?? -1)
  const onKey = (e) => {
    if (e.target.closest && e.target.closest("input, textarea")) return
    const k = e.key.toUpperCase()
    const i = "1234".indexOf(k) >= 0 ? "1234".indexOf(k) : "ABCD".indexOf(k)
    if (i >= 0 && k.length === 1) pick(i)
  }
  document.addEventListener("keydown", onKey)
  return () => document.removeEventListener("keydown", onKey)
}
""",
)


def choice_grid(choices: list, selected: int | None, key: str) -> int | None:
    is_svg = bool(choices) and str(choices[0]).startswith("<svg")
    content = [str(c) if is_svg else html_lib.escape(str(c)) for c in choices]
    r = _CHOICES(key=key, data={"token": key, "choices": content, "selected": selected, "svg": is_svg},
                 default={"selected": selected}, on_selected_change=lambda: None)
    return r.selected


# ---------------------------------------------------------------- 숫자 따라 하기

_DIGIT_SPAN = st.components.v2.component(
    "ltr_digit_span",
    html="<div class='center'></div>",
    css=BASE_CSS + """
.stage { width: 140px; height: 140px; border-radius: 16px; background: var(--bg2); display: flex;
         align-items: center; justify-content: center; font-size: 84px; font-weight: 800; }
.slots { display: flex; gap: 6px; min-height: 52px; }
.slot { width: 40px; height: 52px; border-bottom: 3px solid var(--bd); font-size: 32px; font-weight: 700;
        display: flex; align-items: center; justify-content: center; }
.pad { display: grid; grid-template-columns: repeat(3, 72px); gap: 8px; }
.pad button { height: 56px; font-size: 22px; border-radius: 10px; border: 1px solid var(--bd);
              background: var(--bg2); color: var(--txt); }
""",
    js="""
export default function (component) {
  const { data, parentElement, setTriggerValue, setStateValue } = component
  const root = parentElement.querySelector(".center")
  if (root.dataset.token === data.token) return
  root.dataset.token = data.token
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  let typed = "", t0 = 0, done = false

  const ready = () => {
    root.innerHTML = `<div class="hint">${data.instruction}</div>
      <div class="stage"></div><button class="btn pri">시작</button>`
    root.querySelector("button").onclick = show
  }
  const show = async () => {
    setStateValue("started", true)
    root.innerHTML = `<div class="hint">집중하세요</div><div class="stage"></div>`
    const stage = root.querySelector(".stage")
    await sleep(700)
    for (const d of data.digits) {
      stage.textContent = d
      await sleep(data.show_ms)
      stage.textContent = ""
      await sleep(data.gap_ms)
    }
    input()
  }
  const input = () => {
    root.innerHTML = `<div class="hint">${data.ask}</div><div class="slots"></div>
      <div class="pad"></div><button class="btn pri" disabled>확인</button>`
    const pad = root.querySelector(".pad")
    ;["1","2","3","4","5","6","7","8","9","←","0",""].forEach((k) => {
      const b = document.createElement("button")
      b.textContent = k
      if (!k) b.style.visibility = "hidden"
      b.onclick = () => press(k)
      pad.appendChild(b)
    })
    root.querySelector(".btn.pri").onclick = submit
    t0 = performance.now()
    render()
  }
  const render = () => {
    root.querySelector(".slots").innerHTML = Array.from({ length: data.length },
      (_, i) => `<div class="slot">${typed[i] ?? ""}</div>`).join("")
    root.querySelector(".btn.pri").disabled = typed.length !== data.length
  }
  const press = (k) => {
    if (done) return
    if (k === "←") typed = typed.slice(0, -1)
    else if (/^[0-9]$/.test(k) && typed.length < data.length) typed += k
    render()
  }
  const submit = () => {
    if (done || typed.length !== data.length) return
    done = true
    setTriggerValue("done", { answer: typed, rt_ms: Math.round(performance.now() - t0) })
  }
  const onKey = (e) => {
    if (!root.querySelector(".pad")) return
    if (/^[0-9]$/.test(e.key)) press(e.key)
    else if (e.key === "Backspace") press("←")
    else if (e.key === "Enter") submit()
  }
  document.addEventListener("keydown", onKey)
  ready()
  return () => document.removeEventListener("keydown", onKey)
}
""",
)


def digit_span(token: str, digits: str, mode: str, show_ms: int, gap_ms: int):
    """(완료 trigger, 제시 시작 여부). 제시가 시작된 문항을 새로고침하면 다시 볼 수 없게 하는 데 쓴다."""
    instruction = {"forward": "숫자가 하나씩 나타납니다. 본 순서 <b>그대로</b> 기억하세요.",
                   "backward": "숫자가 하나씩 나타납니다. 나중에 <b>거꾸로</b> 입력합니다.",
                   "sorting": "숫자가 하나씩 나타납니다. 나중에 <b>작은 수부터</b> 입력합니다."}[mode]
    ask = {"forward": "본 순서 그대로 입력하세요", "backward": "본 순서의 거꾸로 입력하세요",
           "sorting": "작은 수부터 큰 수 순서로 입력하세요"}[mode]
    r = _DIGIT_SPAN(key=f"ds-{token}", data={"token": token, "digits": list(digits), "length": len(digits),
                                             "show_ms": show_ms, "gap_ms": gap_ms, "instruction": instruction,
                                             "ask": ask},
                    default={"started": False}, on_started_change=lambda: None, on_done_change=lambda: None)
    return r.done, r.started


# ---------------------------------------------------------------- 위치 기억

_SPATIAL = st.components.v2.component(
    "ltr_spatial_span",
    html="<div class='center'></div>",
    css=BASE_CSS + """
.board { display: grid; gap: 8px; }
.cell { width: 64px; height: 64px; border-radius: 10px; border: 2px solid var(--bd); background: var(--bg2);
        font-size: 18px; font-weight: 700; color: #fff; }
.cell.lit { background: var(--pri); border-color: var(--pri); }
.cell.pick { background: color-mix(in srgb, var(--pri) 70%, transparent); border-color: var(--pri); }
.row { display: flex; gap: 8px; }
""",
    js="""
export default function (component) {
  const { data, parentElement, setTriggerValue, setStateValue } = component
  const root = parentElement.querySelector(".center")
  if (root.dataset.token === data.token) return
  root.dataset.token = data.token
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  let picks = [], t0 = 0, accepting = false, done = false

  const board = () => {
    const b = document.createElement("div")
    b.className = "board"
    b.style.gridTemplateColumns = `repeat(${data.grid}, 64px)`
    for (let i = 0; i < data.grid * data.grid; i++) {
      const c = document.createElement("button")
      c.className = "cell"
      c.dataset.i = i
      c.onclick = () => pick(i, c)
      b.appendChild(c)
    }
    return b
  }
  const ready = () => {
    root.innerHTML = `<div class="hint">칸이 하나씩 켜집니다. <b>켜진 순서</b>를 기억했다가 같은 순서로 누르세요.</div>`
    root.appendChild(board())
    const btn = document.createElement("button")
    btn.className = "btn pri"
    btn.textContent = "시작"
    btn.onclick = show
    root.appendChild(btn)
  }
  const show = async () => {
    setStateValue("started", true)
    root.querySelector(".btn").remove()
    root.querySelector(".hint").textContent = "집중하세요"
    const cells = root.querySelectorAll(".cell")
    await sleep(700)
    for (const i of data.sequence) {
      cells[i].classList.add("lit")
      await sleep(data.show_ms)
      cells[i].classList.remove("lit")
      await sleep(data.gap_ms)
    }
    root.querySelector(".hint").textContent = `켜진 순서대로 ${data.sequence.length}칸을 누르세요`
    const row = document.createElement("div")
    row.className = "row"
    row.innerHTML = `<button class="btn" data-a="reset">다시</button><button class="btn pri" data-a="ok" disabled>확인</button>`
    row.querySelector("[data-a=reset]").onclick = reset
    row.querySelector("[data-a=ok]").onclick = submit
    root.appendChild(row)
    accepting = true
    t0 = performance.now()
  }
  const pick = (i, c) => {
    if (!accepting || done || picks.includes(i) || picks.length >= data.sequence.length) return
    picks.push(i)
    c.classList.add("pick")
    c.textContent = picks.length
    root.querySelector("[data-a=ok]").disabled = picks.length !== data.sequence.length
  }
  const reset = () => {
    picks = []
    root.querySelectorAll(".cell").forEach((c) => { c.classList.remove("pick"); c.textContent = "" })
    root.querySelector("[data-a=ok]").disabled = true
  }
  const submit = () => {
    if (done || picks.length !== data.sequence.length) return
    done = true
    setTriggerValue("done", { answer: picks.join(","), rt_ms: Math.round(performance.now() - t0) })
  }
  ready()
}
""",
)


def spatial_span(token: str, grid: int, sequence: list[int], show_ms: int, gap_ms: int):
    r = _SPATIAL(key=f"ss-{token}", data={"token": token, "grid": grid, "sequence": sequence,
                                          "show_ms": show_ms, "gap_ms": gap_ms},
                 default={"started": False}, on_started_change=lambda: None, on_done_change=lambda: None)
    return r.done, r.started


# ---------------------------------------------------------------- 기호 바꾸기

_SYMBOL = st.components.v2.component(
    "ltr_symbol_coding",
    html="<div class='center'></div>",
    css=BASE_CSS + """
.legend { display: grid; grid-template-columns: repeat(9, 44px); border: 1px solid var(--bd); border-radius: 8px;
          overflow: hidden; }
.legend div { text-align: center; padding: 4px 0; border-right: 1px solid var(--bd); }
.legend div:last-child { border-right: 0; }
.legend .g { font-size: 22px; } .legend .n { font-weight: 700; border-top: 1px solid var(--bd); }
.big { font-size: 72px; width: 120px; height: 120px; display: flex; align-items: center; justify-content: center;
       border-radius: 16px; background: var(--bg2); }
.big.ok { box-shadow: 0 0 0 4px #16a34a; } .big.no { box-shadow: 0 0 0 4px #dc2626; }
.pad { display: grid; grid-template-columns: repeat(9, 44px); gap: 4px; }
.pad button { height: 48px; font-size: 20px; border-radius: 8px; border: 1px solid var(--bd);
              background: var(--bg2); color: var(--txt); }
.time { font-weight: 700; font-variant-numeric: tabular-nums; }
@media (max-width: 480px) { .legend, .pad { grid-template-columns: repeat(9, 34px); } }
""",
    js="""
export default function (component) {
  const { data, parentElement, setTriggerValue, setStateValue } = component
  const root = parentElement.querySelector(".center")
  if (root.dataset.token === data.token) return
  root.dataset.token = data.token
  const legend = `<div class="legend">${data.symbols.map((g, i) =>
    `<div><div class="g">${g}</div><div class="n">${i + 1}</div></div>`).join("")}</div>`
  let mode = "idle", idx = 0, correct = 0, wrong = 0, endAt = 0, timer = null, practiceLeft = 3

  const screen = (hint, withPad) => {
    root.innerHTML = `${legend}<div class="hint">${hint}</div><div class="big"></div>` +
      (withPad ? `<div class="pad">${[1,2,3,4,5,6,7,8,9].map((n) => `<button>${n}</button>`).join("")}</div>` : "")
    root.querySelectorAll(".pad button").forEach((b) => (b.onclick = () => answer(Number(b.textContent))))
  }
  const current = () => data.sequence[idx % data.sequence.length]
  const showSymbol = () => { root.querySelector(".big").textContent = data.symbols[current()] }
  const intro = () => {
    screen("위 표에서 가운데 기호에 해당하는 숫자를 누르세요. 먼저 3번 연습합니다.", false)
    const b = document.createElement("button")
    b.className = "btn pri"; b.textContent = "연습 시작"
    b.onclick = () => { mode = "practice"; screen("연습 중 (채점하지 않음)", true); showSymbol() }
    root.appendChild(b)
  }
  const ready = () => {
    mode = "idle"
    screen(`연습 끝! 본 검사는 ${data.duration_sec}초 동안 최대한 빠르고 정확하게 누르세요.`, false)
    const b = document.createElement("button")
    b.className = "btn pri"; b.textContent = "본 검사 시작"
    b.onclick = start
    root.appendChild(b)
  }
  const start = () => {
    setStateValue("started", true)
    mode = "test"; idx = 0; correct = 0; wrong = 0
    screen(`남은 시간 <span class="time"></span>초`, true)
    endAt = performance.now() + data.duration_sec * 1000
    showSymbol()
    timer = setInterval(() => {
      const left = Math.max(0, endAt - performance.now())
      const t = root.querySelector(".time"); if (t) t.textContent = Math.ceil(left / 1000)
      if (left <= 0) finish()
    }, 200)
  }
  const flash = (ok) => {
    const big = root.querySelector(".big")
    big.classList.remove("ok", "no"); big.classList.add(ok ? "ok" : "no")
    setTimeout(() => big.classList.remove("ok", "no"), 150)
  }
  const answer = (n) => {
    if (mode !== "practice" && mode !== "test") return
    const ok = n === current() + 1
    if (mode === "practice") {
      flash(ok)
      if (!ok) return
      idx += 1; practiceLeft -= 1
      if (practiceLeft === 0) { idx = 0; setTimeout(ready, 250); return }
      showSymbol(); return
    }
    ok ? correct++ : wrong++
    idx += 1
    showSymbol()
  }
  const finish = () => {
    if (mode !== "test") return
    mode = "done"; clearInterval(timer)
    screen("끝났습니다. 잠시만 기다려 주세요.", false)
    setTriggerValue("done", { correct, wrong })
  }
  const onKey = (e) => { if (/^[1-9]$/.test(e.key)) answer(Number(e.key)) }
  document.addEventListener("keydown", onKey)
  intro()
  return () => { clearInterval(timer); document.removeEventListener("keydown", onKey) }
}
""",
)


def symbol_coding(token: str, symbols: list[str], sequence: list[int], duration_sec: int):
    r = _SYMBOL(key=f"sc-{token}", data={"token": token, "symbols": symbols, "sequence": sequence,
                                         "duration_sec": duration_sec},
                default={"started": False}, on_started_change=lambda: None, on_done_change=lambda: None)
    return r.done, r.started


# ---------------------------------------------------------------- 결과 카드 (PNG 저장)

_CARD = st.components.v2.component(
    "ltr_result_card",
    html="<div class='wrap'><canvas width='1080' height='1350'></canvas><button class='btn pri'>결과 카드 저장 (PNG)</button></div>",
    css=BASE_CSS + """
.wrap { display: flex; flex-direction: column; align-items: center; gap: 12px; }
canvas { width: 100%; max-width: 360px; height: auto; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.12); }
""",
    js="""
export default function (component) {
  const { data, parentElement } = component
  const cv = parentElement.querySelector("canvas")
  const g = cv.getContext("2d")
  const W = 1080, H = 1350, P = "#4F46E5"
  const font = (w, s) => `${w} ${s}px "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", sans-serif`
  g.fillStyle = "#ffffff"; g.fillRect(0, 0, W, H)
  g.fillStyle = P; g.fillRect(0, 0, W, 300)
  g.fillStyle = "#ffffff"; g.textAlign = "center"
  g.font = font(600, 40); g.fillText("종합사고지수 LTR Index", W / 2, 110)
  g.font = font(800, 150); g.fillText(Math.round(data.index), W / 2, 260)
  g.fillStyle = "#111827"
  g.font = font(700, 52); g.fillText(`${data.position} · ${data.level}`, W / 2, 390)
  g.fillStyle = "#6b7280"; g.font = font(400, 34)
  g.fillText(`${data.mode} · IQ 척도(평균 100) 기준`, W / 2, 450)

  // 레이더: 55~145를 반지름에 대응, 100 기준선
  const cx = W / 2, cy = 860, R = 300, lo = 55, hi = 145
  const n = data.domains.length
  const pt = (i, v) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n
    const r = (Math.min(Math.max(v, lo), hi) - lo) / (hi - lo) * R
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
  }
  g.strokeStyle = "#e5e7eb"; g.lineWidth = 2
  for (const v of [70, 85, 115, 130, 145]) {
    g.beginPath(); data.domains.forEach((_, i) => { const [x, y] = pt(i, v); i ? g.lineTo(x, y) : g.moveTo(x, y) })
    g.closePath(); g.stroke()
  }
  g.setLineDash([10, 8]); g.strokeStyle = "#9ca3af"
  g.beginPath(); data.domains.forEach((_, i) => { const [x, y] = pt(i, 100); i ? g.lineTo(x, y) : g.moveTo(x, y) })
  g.closePath(); g.stroke(); g.setLineDash([])
  g.strokeStyle = "#e5e7eb"
  data.domains.forEach((_, i) => { const [x, y] = pt(i, hi); g.beginPath(); g.moveTo(cx, cy); g.lineTo(x, y); g.stroke() })
  g.beginPath()
  data.domains.forEach((d, i) => { const [x, y] = pt(i, d.index); i ? g.lineTo(x, y) : g.moveTo(x, y) })
  g.closePath(); g.fillStyle = "rgba(79,70,229,.22)"; g.fill(); g.strokeStyle = P; g.lineWidth = 5; g.stroke()
  data.domains.forEach((d, i) => {
    const [x, y] = pt(i, d.index)
    g.beginPath(); g.arc(x, y, 10, 0, 2 * Math.PI); g.fillStyle = P; g.fill()
    const [lx, ly] = pt(i, hi + 26)
    g.fillStyle = "#111827"; g.font = font(700, 36); g.fillText(d.label, lx, ly)
    g.fillStyle = P; g.font = font(700, 32); g.fillText(Math.round(d.index), lx, ly + 40)
  })
  g.fillStyle = "#9ca3af"; g.font = font(400, 28)
  g.fillText(`${data.date} · 온라인 인지능력 테스트이며 전문 심리검사를 대체하지 않습니다`, W / 2, H - 50)

  parentElement.querySelector("button").onclick = () => {
    const a = document.createElement("a")
    a.download = `LTR-${Math.round(data.index)}.png`
    a.href = cv.toDataURL("image/png")
    a.click()
  }
}
""",
)


def result_card(index: float, position: str, level: str, mode: str, date: str, domains: list[dict]) -> None:
    """domains: [{"label": "유동추론", "index": 108.2}, ...]"""
    _CARD(key="result-card", data={"index": index, "position": position, "level": level, "mode": mode, "date": date,
                                   "domains": domains})
