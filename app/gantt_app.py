"""Streamlit 演示：滑动条调换型时间，左右对比「无换型」与「含换型」的甘特图。

启动（在仓库根目录）：
    streamlit run app/gantt_app.py

它做的事情：
    1. 选算例、产品族数、跨族换型时间、求解时间上限；
    2. 阶段一求无换型最优，阶段二在机器固定的前提下插入换型；
    3. 上下两张甘特图 + 一行关键指标（makespan、涨幅、换型占比）。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import matplotlib          # noqa: E402
matplotlib.use("Agg")
import streamlit as st     # noqa: E402

from fjsp_parser import load_brandimarte                        # noqa: E402
from model_cpsat import solve as solve_phase1                   # noqa: E402
from model_setup import assign_from_plan, solve_phase2          # noqa: E402
from plot_gantt import build_figure                             # noqa: E402
from setup_matrix import assign_families, build_matrix          # noqa: E402
from verify import verify_plan                                  # noqa: E402

st.set_page_config(page_title="FJSP 排产演示", layout="wide")


@st.cache_data(show_spinner=False)
def run_case(path, families_k, setup_s, limit):
    jobs, n_mach = load_brandimarte(path)
    families = assign_families(len(jobs), families_k)
    matrix = build_matrix(families_k, setup_s)

    p1 = solve_phase1(jobs, n_mach, time_limit=limit)
    if not p1["plan"]:
        raise RuntimeError("阶段一无解：%s" % p1["status"])
    verify_plan(jobs, n_mach, p1["plan"])

    if setup_s == 0:
        p2 = None
    else:
        assign = assign_from_plan(jobs, p1["plan"])
        p2 = solve_phase2(jobs, n_mach, assign, families, matrix,
                          time_limit=limit, hint_plan=p1["plan"])
        if not p2["plan"]:
            raise RuntimeError("阶段二无解：%s" % p2["status"])
        verify_plan(jobs, n_mach, p2["plan"])

    return {
        "jobs": jobs, "n_mach": n_mach, "families": families, "matrix": matrix,
        "p1": {k: p1[k] for k in ("status", "makespan", "plan")},
        "p2": ({k: p2[k] for k in ("status", "makespan", "plan", "total_setup")}
               if p2 else None),
    }


def main():
    st.title("FJSP 排产演示：换型时间如何吃掉产能")
    st.caption("阶段一定机器、阶段二排序列并插入换型；所有结果都通过四项结构校验。")

    data_dir = ROOT / "data"
    files = sorted(p.name for p in data_dir.glob("*.txt")) if data_dir.exists() else []

    with st.sidebar:
        st.header("参数")
        if not files:
            st.error("找不到 data/*.txt，请把算例放进仓库的 data/ 目录")
            return
        name = st.selectbox("算例", files, index=0)
        families_k = st.slider("产品族数", 2, 5, 3)
        setup_s = st.slider("跨族换型时间 s", 0, 120, 45, step=5)
        limit = st.slider("求解时间上限（秒）", 5, 300, 60, step=5)
        st.caption("s=0 表示假设换型为 0（教科书写法），用来做对照。")

    path = str(data_dir / name)
    try:
        with st.spinner("求解中…"):
            res = run_case(path, families_k, setup_s, float(limit))
    except Exception as exc:                      # noqa: BLE001
        st.error("求解失败：%s" % exc)
        return

    p1, p2 = res["p1"], res["p2"]
    mk0 = p1["makespan"]
    mk1 = p2["makespan"] if p2 else mk0
    inc = (mk1 - mk0) * 100.0 / mk0 if mk0 else 0.0
    per_mach = (p2["total_setup"] / float(res["n_mach"])) if p2 else 0.0
    share = per_mach * 100.0 / mk1 if mk1 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("无换型 makespan", "%d" % mk0, p1["status"])
    c2.metric("含换型 makespan", "%d" % mk1,
              "%+.1f%%" % inc if p2 else "—", delta_color="inverse")
    c3.metric("换型总量", "%d" % (p2["total_setup"] if p2 else 0))
    c4.metric("单机换型占机时", "%.1f%%" % share)

    fig1, _ = build_figure(res["jobs"], res["n_mach"], p1["plan"], res["families"],
                           res["matrix"], title="① 无换型（阶段一最优，makespan=%d）" % mk0)
    st.pyplot(fig1)

    if p2:
        fig2, _ = build_figure(res["jobs"], res["n_mach"], p2["plan"], res["families"],
                               res["matrix"],
                               title="② 含换型 s=%d（makespan=%d，斜线为换型）" % (setup_s, mk1))
        st.pyplot(fig2)
        st.info("同一批工序，加进换型后完工时间上升 %.1f%%；斜线段就是被换型吃掉的产能。" % inc)
    else:
        st.info("s=0 时无换型，两张图相同。")


if __name__ == "__main__":
    main()