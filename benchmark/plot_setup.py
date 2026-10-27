"""把 results/setup.csv 画成「换型强度 → makespan 涨幅」曲线。

用法（仓库根目录）：
    python benchmark/plot_setup.py
输出：results/setup_curve.png
"""
import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main(csv_path=None, out=None):
    csv_path = pathlib.Path(csv_path or ROOT / "results" / "setup.csv")
    out = pathlib.Path(out or ROOT / "results" / "setup_curve.png")
    if not csv_path.exists():
        print("找不到 %s，先跑 benchmark/run_setup.py" % csv_path)
        return 1

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    series = {}
    for r in rows:
        series.setdefault(r["instance"], []).append(
            (float(r["setup_over_mean"]), float(r["increase_pct"]),
             float(r["setup_share_pct"]), r["status"]))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("没装 matplotlib，跳过画图")
        return 0

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9.6, 3.6), dpi=160)
    colors = {"mk01": "#1f3864", "mk05": "#c00000", "mk07": "#2e75b6"}
    for name, pts in series.items():
        pts.sort()
        xs = [p[0] for p in pts if p[0] > 0]
        ys = [p[1] for p in pts if p[0] > 0]
        ss = [p[2] for p in pts if p[0] > 0]
        ax.plot(xs, ys, "o-", ms=3.6, lw=1.4, color=colors.get(name, None), label=name)
        ax2.plot(xs, ss, "o-", ms=3.6, lw=1.4, color=colors.get(name, None), label=name)

    for a, ylab, title in ((ax, "makespan 涨幅 %", "换型时间越长，排产越被换型拖住"),
                           (ax2, "换型占机时 %", "换型吃掉多少机器时间")):
        a.set_xscale("log")
        a.set_xlabel("换型时间 ÷ 平均工序工时（倍数，对数轴）", fontsize=9)
        a.set_ylabel(ylab, fontsize=9)
        a.set_title(title, fontsize=10, loc="left")
        a.grid(linestyle=":", color="#cccccc")
        a.tick_params(labelsize=8)
        a.legend(fontsize=8, frameon=False)

    fig.tight_layout()
    fig.text(0.01, -0.02,
             "注：s=0 档已单列校验（换型总量必须为 0，证明两阶段分解无损）；"
             "mk05 的部分档位是时间限内的可行解，重跑有 5–8% 波动，曲线非严格单调即由此而来。",
             fontsize=7.2, color="#666666")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    print("图已保存 ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
