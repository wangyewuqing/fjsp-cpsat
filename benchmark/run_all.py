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
    print("%-10s %5s %6s %6s %10s %8s %8s" %
          ("算例", "工件", "机器", "工序", "makespan", "最好解", "gap"))
    print("-" * 60)

    for f in files:
        name = f.stem
        jobs, n_mach, n_ops, _ = summarize(f)
        t0 = time.perf_counter()
        mk, plan = list_schedule(jobs, n_mach)
        rt = time.perf_counter() - t0
        span = verify_plan(jobs, n_mach, plan)      # 校验不过直接抛异常
        if span != mk:
            raise AssertionError("%s: 报表 makespan %d 与重算 %d 不一致" % (name, mk, span))
        best = BEST_KNOWN.get(name)
        gap = (mk - best) / best if best else ""
        rows.append({
            "instance": name,
            "jobs": len(jobs),
            "machines": n_mach,
            "ops": n_ops,
            "makespan": mk,
            "best_known": best if best else "",
            "gap_pct": round(gap * 100, 1) if best else "",
            "runtime_s": round(rt, 4),
            "verified": "yes",
        })
        print("%-10s %5d %6d %6d %10d %8s %7s%%" %
              (name, len(jobs), n_mach, n_ops, mk,
               best if best else "-", ("%.1f" % (gap * 100)) if best else "-"))

    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print("-" * 60)
    print("写好了 %d 行 -> %s" % (len(rows), out_csv))
    return 0


if __name__ == "__main__":
    sys.exit(main())