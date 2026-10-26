"""甘特图：把排产方案画成一张能直接放进报告的图。

画法：
    横轴 时间，纵轴 机器；
    加工块按「产品族」着色（同族同色，一眼看出批量）；
    换型块用斜线阴影画在前一道工序结束的位置（宽度 = 换型时间）；
    两者之间的空白就是机器空闲。

用法（在仓库根目录）：
    python src/plot_gantt.py data/mk01.txt --setup 45 --out results/gantt_mk01_s45.png
    python src/plot_gantt.py data/mk01.txt --setup 0  --out results/gantt_mk01_nosetup.png
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import matplotlib                          # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt            # noqa: E402
from matplotlib.patches import Patch       # noqa: E402

from fjsp_parser import load_brandimarte                      # noqa: E402
from model_cpsat import solve as solve_phase1                 # noqa: E402
from model_setup import assign_from_plan, solve_phase2        # noqa: E402
from setup_matrix import assign_families, build_matrix        # noqa: E402
from verify import verify_plan                                # noqa: E402

FAMILY_COLORS = ["#1f3864", "#2e75b6", "#8faadc", "#c0392b", "#7f7f7f", "#bf9000"]

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def split_segments(jobs, n_mach, plan, families, matrix):
    """把计划拆成 (加工段, 换型段)。换型段从上一道工序结束处开始，宽度取换型时间。"""
    per_mach = {}
    for j, m, st, fin in plan:
        per_mach.setdefault(m, []).append((st, fin, j))

    proc, setup = [], []
    for m, seq in per_mach.items():
        seq.sort()
        for j, (st, fin, jid) in enumerate(seq):
            proc.append({"mach": m, "start": st, "end": fin,
                         "job": jid, "family": families[jid]})
            if j + 1 < len(seq):
                nxt = seq[j + 1][2]
                s = matrix[families[jid]][families[nxt]]
                if s:
                    setup.append({"mach": m, "start": fin, "end": fin + s,
                                  "from": families[jid], "to": families[nxt]})
    return proc, setup


def build_figure(jobs, n_mach, plan, families, matrix, title="", figsize=None,
                 annotate=True):
    """返回一个 matplotlib Figure。"""
    proc, setup = split_segments(jobs, n_mach, plan, families, matrix)
    k = len(set(families))
    figsize = figsize or (11.5, max(3.0, 0.55 * n_mach + 1.6))
    fig, ax = plt.subplots(figsize=figsize, dpi=150)

    span = 0
    for seg in proc:
        fam = seg["family"] % len(FAMILY_COLORS)
        ax.barh(seg["mach"], seg["end"] - seg["start"], left=seg["start"],
                height=0.62, color=FAMILY_COLORS[fam], edgecolor="white",
                linewidth=0.8, zorder=2)
        span = max(span, seg["end"])
        if annotate and (seg["end"] - seg["start"]) >= max(2, span * 0.022):
            ax.text((seg["start"] + seg["end"]) / 2.0, seg["mach"], str(seg["job"]),
                    ha="center", va="center", fontsize=6.5, color="white", zorder=3)

    for seg in setup:
        ax.barh(seg["mach"], seg["end"] - seg["start"], left=seg["start"],
                height=0.62, color="#f2f2f2", edgecolor="#808080", linewidth=0.5,
                hatch="////", zorder=2)
        span = max(span, seg["end"])

    ax.set_yticks(range(n_mach))
    ax.set_yticklabels(["机器 %d" % (m + 1) for m in range(n_mach)], fontsize=8)
    ax.set_xlabel("时间", fontsize=9)
    ax.set_ylabel("机器", fontsize=9)
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle=":", linewidth=0.6, color="#cccccc", zorder=0)
    ax.set_xlim(0, span * 1.04 if span else 1)
    ax.set_ylim(n_mach - 0.35, -0.95)          # 反转纵轴，机器 1 在最上面
    makespan = max((s["end"] for s in proc), default=0)
    ax.axvline(makespan, color="#c0392b", linestyle="--", linewidth=1.0, zorder=4)
    ax.text(makespan, -0.72, "makespan = %d " % makespan, color="#c0392b",
            fontsize=8.5, va="bottom", ha="right", fontweight="bold",
            bbox=dict(facecolor="white", edgecolor="none", pad=1.5))

    handles = [Patch(facecolor=FAMILY_COLORS[f % len(FAMILY_COLORS)],
                     label="族 %d" % f) for f in range(k)]
    handles.append(Patch(facecolor="#f2f2f2", edgecolor="#808080", hatch="////",
                         label="换型"))
    ax.legend(handles=handles, loc="upper center", fontsize=8, ncol=k + 1,
              frameon=False, bbox_to_anchor=(0.5, -0.16))

    if title:
        ax.set_title(title, fontsize=10.5, loc="left", pad=10)
    fig.tight_layout()
    return fig, {"makespan": makespan,
                 "setup_total": sum(s["end"] - s["start"] for s in setup),
                 "n_setup": len(setup),
                 "n_proc": len(proc)}


def plot_plan(jobs, n_mach, plan, families, matrix, out_path, title="", **kw):
    fig, stats = build_figure(jobs, n_mach, plan, families, matrix, title=title, **kw)
    out_path = pathlib.Path(out_path)
    if str(out_path.parent):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return stats


def main():
    ap = argparse.ArgumentParser(description="把 FJSP 排产方案画成甘特图")
    ap.add_argument("instance", nargs="?", default="data/mk01.txt")
    ap.add_argument("--setup", type=int, default=45, help="跨族换型时间（0 = 假设换型为 0）")
    ap.add_argument("--families", type=int, default=3, help="产品族数量")
    ap.add_argument("--limit", type=float, default=300.0, help="求解时间上限（秒）")
    ap.add_argument("--out", default="results/gantt.png")
    ap.add_argument("--no-annotate", action="store_true", help="不在工序块上写工件号")
    args = ap.parse_args()

    jobs, n_mach = load_brandimarte(args.instance)
    families = assign_families(len(jobs), args.families)
    matrix = build_matrix(args.families, args.setup)

    p1 = solve_phase1(jobs, n_mach, time_limit=args.limit)
    if not p1["plan"]:
        print("阶段一没解出来：", p1["status"])
        return 1
    verify_plan(jobs, n_mach, p1["plan"])
    print("阶段一（无换型）：%s  makespan = %d" % (p1["status"], p1["makespan"]))

    if args.setup == 0:
        plan, makespan, status = p1["plan"], p1["makespan"], p1["status"]
    else:
        assign = assign_from_plan(jobs, p1["plan"])
        p2 = solve_phase2(jobs, n_mach, assign, families, matrix,
                          time_limit=args.limit, hint_plan=p1["plan"])
        if not p2["plan"]:
            print("阶段二没解出来：", p2["status"])
            return 1
        verify_plan(jobs, n_mach, p2["plan"])
        plan, makespan, status = p2["plan"], p2["makespan"], p2["status"]
        print("阶段二（s=%d, %d 族）：%s  makespan = %d  换型总量 %d"
              % (args.setup, args.families, status, makespan, p2["total_setup"]))

    title = "%s ｜ s=%d ｜ %d 族 ｜ makespan=%d ｜ %s" % (
        pathlib.Path(args.instance).stem, args.setup, args.families, makespan, status)
    stats = plot_plan(jobs, n_mach, plan, families, matrix, args.out, title=title,
                      annotate=not args.no_annotate)
    print("统计：工序块 %d / 换型段 %d / 换型总量 %d" %
          (stats["n_proc"], stats["n_setup"], stats["setup_total"]))
    print("图已保存 ->", pathlib.Path(args.out).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
