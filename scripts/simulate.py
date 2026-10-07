"""가상 응시 데이터 생성 (로컬 개발·분석 화면 확인용): python scripts/simulate.py [--n 300] [--reset]

- 능력 θ ~ N(0, 1)인 가상 응시자가 실제 출제·라우팅 로직(core.exam)으로 검사를 풉니다.
- 문항의 '참 난이도'를 가정값에서 조금씩 흔들고, 일부 문항은 일부러 아주 쉽게/어렵게 만들어
  관리자 분석이 그런 문항을 찾아내는지 확인할 수 있게 합니다.
- 세션의 app_version이 "sim"이라 규준 계산에서 빠지고, 분석 화면에서도 기본으로 제외됩니다.
- --reset 은 기존 시뮬레이션 데이터만 지웁니다.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import db  # noqa: E402
from core import exam as ex  # noqa: E402
from core import scoring as sc  # noqa: E402
from core.analysis import SIM_VERSION  # noqa: E402
from core.item_bank import build_form, load_items  # noqa: E402
from core.schema import Domain, ItemFormat, Mode  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=300)
ap.add_argument("--reset", action="store_true")
ap.add_argument("--db", default=str(ROOT / "data" / "iq_test.db"))
args = ap.parse_args()

engine = sa.create_engine(f"sqlite:///{Path(args.db).as_posix()}")
db.init_db(engine)
with engine.begin() as conn:
    sim_ids = [r.id for r in conn.execute(sa.select(db.sessions.c.id).where(db.sessions.c.app_version == SIM_VERSION))]
    conn.execute(db.responses.delete().where(db.responses.c.session_id.in_(sim_ids)))
    conn.execute(db.sessions.delete().where(db.sessions.c.app_version == SIM_VERSION))
print(f"기존 시뮬레이션 세션 {len(sim_ids)}개 삭제")
if args.reset:
    sys.exit()

items_list = load_items()
items = {it.id: it for it in items_list}
rng = random.Random(7)

# 참 난이도: 가정 b에 잡음을 더하고, 일부 문항은 일부러 크게 어긋나게 한다
true_b = {}
planted = {}
for it in items_list:
    a, b, c = sc.item_params(it)
    true_b[it.id] = b + rng.gauss(0, 0.3)
mcq = [it.id for it in items_list if it.format is ItemFormat.MCQ]
for iid in rng.sample(mcq, 12):
    shift = rng.choice([-2.5, 2.5])
    true_b[iid] += shift
    planted[iid] = "실제로 훨씬 쉬움" if shift < 0 else "실제로 훨씬 어려움"


def p_correct(item_id: str, theta: float) -> float:
    a, _, c = sc.item_params(items[item_id])
    return c + (1 - c) / (1 + np.exp(-sc.D * a * (theta - true_b[item_id])))


def answer(item_id: str, theta: float, seed: int) -> str:
    it = items[item_id]
    ok = rng.random() < p_correct(item_id, theta)
    if it.format is ItemFormat.MCQ:
        return str(it.answer if ok else rng.choice([k for k in range(4) if k != it.answer]))
    if it.format is ItemFormat.SYMBOL_CODING:
        s = max(0, round(sc.GS_MEAN + sc.GS_SD * (0.9 * theta + rng.gauss(0, 0.45))))
        return json.dumps({"correct": s + 2, "wrong": 2})
    expected = ex.wm_stimulus(it, seed)["expected"]
    return expected if ok else ""


def run_round(theta: float, mode: Mode, client: str, series: str | None, round_no: int, seen: set) -> tuple[str, set]:
    seed = rng.randrange(2**31)
    sid = db.start_session(engine, client, mode.value, seed, SIM_VERSION, series_id=series, round_no=round_no)
    state = ex.new_exam(build_form(items_list, seed, mode, exclude=seen), mode)
    all_rows = []
    while state["d"] < len(state["domains"]):
        d = ex.current_domain(state)
        for iid in state["items"][d.value]:
            state["answers"][iid] = answer(iid, theta, seed)
            state["ms"][iid] = int(rng.lognormvariate(8.8 + 0.25 * items[iid].difficulty, 0.4))  # 약 9~19초
        if ex.has_stage2(state):
            ex.route_domain(state, items, seed)
            for iid in state["items"][d.value][state["stage1_n"][d.value]:]:
                state["answers"][iid] = answer(iid, theta, seed)
                state["ms"][iid] = int(rng.lognormvariate(8.8 + 0.25 * items[iid].difficulty, 0.4))
        rows = ex.domain_rows(state, items, d, seed)
        db.save_responses(engine, sid, rows)
        all_rows += rows
        ex.finish_domain(state, rows)
    per, total = sc.estimate(all_rows, items)
    db.save_progress(engine, sid, state)
    db.complete_session(engine, sid, {d.value: e.raw for d, e in per.items()},
                        {d.value: round(e.index, 1) for d, e in per.items()}, round(total.index, 1),
                        round(sc.percentile(total.theta), 1),
                        thetas={"total": total.theta, **{d.value: e.theta for d, e in per.items()}},
                        focus_lost=rng.choice([0, 0, 0, 1, 2]))
    return sid, {r["item_id"] for r in all_rows}


thetas = []
for i in range(args.n):
    theta = rng.gauss(0, 1)
    mode = Mode.QUICK if rng.random() < 0.6 else Mode.FULL
    sid, seen = run_round(theta, mode, f"sim-{i}", None, 1, set())
    thetas.append(theta)
    if rng.random() < 0.3:  # 30%는 2라운드까지
        run_round(theta + 0.1, mode, f"sim-{i}", sid, 2, seen)
    if (i + 1) % 50 == 0:
        print(f"  {i + 1}/{args.n}명")

print(f"시뮬레이션 응시자 {args.n}명 저장 (app_version='{SIM_VERSION}')")
print("일부러 어긋나게 만든 문항:", json.dumps(planted, ensure_ascii=False))
