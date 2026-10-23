"""一键跑全集：遍历 data/*.txt，跑派工基线，做四项校验，写 results/baseline.csv。

用法（在仓库根目录）：
    python benchmark/run_all.py
    python benchmark/run_all.py --data data --out results/baseline.csv
"""
import csv
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fjsp_parser import summarize            # noqa: E402
from src.baseline import list_schedule      # noqa: E402
from src.verify import verify_plan          # noqa: E402
from src.lower_bound import lower_bound     # noqa: E402

# Brandimarte MK01-MK10 的公开最好解（写报告时用它算 gap）
BEST_KNOWN = {
    "mk01": 40, "mk02": 26, "mk03": 204, "mk04": 60, "mk05": 173,
    "mk06": 58, "mk07": 139, "mk08": 523, "mk09": 307, "mk10": 197,
}


def main():
    argv = sys.argv[1:]

    def arg(name, default):
        if name in argv:
            return argv[argv.index(name) + 1]
        return default

    data_dir = pathlib.Path(arg("--data", "data"))
    out_csv = pathlib.Path(arg("--out", "results/baseline.csv"))

    files = sorted(data_dir.glob("*.txt"))
    if not files:
        print("没有找到算例：%s 下没有 .txt" % data_dir)
        return 1

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    print("%-9s %4s %4s %5s %9s %7s %7s %8s %6s" %
          ("算例", "工件", "机器", "工序", "makespan", "最好解", "gap", "下界LB", "mk/LB"))
    print("-" * 74)

    for f in files:
        name = f.stem
        jobs, n_mach, n_ops, _, base = summarize(f)
        t0 = time.perf_counter()
        mk, plan = list_schedule(jobs, n_mach)
        rt = time.perf_counter() - t0
        span = verify_plan(jobs, n_mach, plan)      # 校验不过直接抛异常
        if span != mk:
            raise AssertionError("%s: 报表 makespan %d 与重算 %d 不一致" % (name, mk, span))
        lb, _, _ = lower_bound(jobs, n_mach)
        best = BEST_KNOWN.get(name)
        gap = (mk - best) / best if best else ""
        rows.append({
            "instance": name,
            "jobs": len(jobs),
            "machines": n_mach,
            "ops": n_ops,
            "machine_base": base,
            "makespan": mk,
            "best_known": best if best else "",
            "gap_pct": round(gap * 100, 1) if best else "",
            "lower_bound": lb,
            "mk_over_lb": round(mk / lb, 2),
            "runtime_s": round(rt, 4),
            "verified": "yes",
        })
        print("%-9s %4d %4d %5d %9d %7s %6s%% %8d %6.2f" %
              (name, len(jobs), n_mach, n_ops, mk,
               best if best else "-",
               ("%.1f" % (gap * 100)) if best else "-",
               lb, mk / lb))

    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print("-" * 74)
    gaps = [r["gap_pct"] for r in rows if r["gap_pct"] != ""]
    ratios = [r["mk_over_lb"] for r in rows]
    if gaps:
        print("gap 区间 %.1f%% – %.1f%%，平均 %.1f%%"
              % (min(gaps), max(gaps), sum(gaps) / len(gaps)))
    print("mk/LB 区间 %.2f – %.2f，平均 %.2f（派工规则做到 1.6–2.2 属正常）"
          % (min(ratios), max(ratios), sum(ratios) / len(ratios)))
    print("写好了 %d 行 -> %s" % (len(rows), out_csv))
    return 0


if __name__ == "__main__":
    sys.exit(main())