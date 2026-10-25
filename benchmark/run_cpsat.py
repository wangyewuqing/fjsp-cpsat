"""CP-SAT 与派工基线的横向对比：跑指定算例、逐项校验、写 results/cpsat.csv。

用法（在仓库根目录）：
    python benchmark/run_cpsat.py                       # 默认跑 mk01,mk03，每个 60 秒
    python benchmark/run_cpsat.py --instances mk01,mk03,mk10 --limit 300
    python benchmark/run_cpsat.py --no-hint             # 不给初始提示，对比加速效果
"""
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fjsp_parser import summarize            # noqa: E402
from src.baseline import list_schedule      # noqa: E402
from src.verify import verify_plan          # noqa: E402
from src.lower_bound import lower_bound     # noqa: E402
from src.model_cpsat import solve           # noqa: E402

BEST_KNOWN = {
    "mk01": 40, "mk02": 26, "mk03": 204, "mk04": 60, "mk05": 173,
    "mk06": 58, "mk07": 139, "mk08": 523, "mk09": 307, "mk10": 197,
}


def main():
    argv = sys.argv[1:]

    def arg(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    data_dir = pathlib.Path(arg("--data", "data"))
    names = [s.strip() for s in arg("--instances", "mk01,mk03").split(",") if s.strip()]
    limit = float(arg("--limit", "60"))
    use_hint = "--no-hint" not in argv
    out_csv = pathlib.Path(arg("--out", "results/cpsat.csv"))
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    print("%-6s %5s %6s %8s %9s %6s %9s %9s %8s" %
          ("算例", "工序", "机器", "派工", "CP-SAT", "状态", "改善", "对最好解", "用时s"))
    print("-" * 78)

    for name in names:
        f = data_dir / (name + ".txt")
        if not f.exists():
            print("%-6s 跳过：找不到 %s" % (name, f))
            continue
        jobs, n_mach, n_ops, _, base = summarize(f)
        lb, _, _ = lower_bound(jobs, n_mach)
        base_mk, base_plan = list_schedule(jobs, n_mach)
        res = solve(jobs, n_mach, time_limit=limit, hint_plan=base_plan if use_hint else None)

        if not res["plan"]:
            print("%-6s 无可行解：%s" % (name, res["status"]))
            rows.append({
                "instance": name, "ops": n_ops, "machines": n_mach,
                "baseline": base_mk, "cpsat": "", "status": res["status"],
                "improve_pct": "", "gap_vs_best_pct": "", "bound": lb,
                "gap_to_bound_pct": "", "time_limit": limit,
                "runtime_s": res["runtime"], "verified": "no",
            })
            continue

        span = verify_plan(jobs, n_mach, res["plan"])          # 与基线用同一套校验
        if span != res["makespan"]:
            raise AssertionError("%s: 报表 %d 与重算 %d 不一致" % (name, res["makespan"], span))

        mk = res["makespan"]
        best = BEST_KNOWN.get(name)
        improve = (base_mk - mk) * 100.0 / base_mk
        gap_best = (mk - best) * 100.0 / best if best else ""
        gap_lb = (mk - res["bound"]) * 100.0 / res["bound"]
        rows.append({
            "instance": name,
            "ops": n_ops,
            "machines": n_mach,
            "baseline": base_mk,
            "cpsat": mk,
            "status": res["status"],
            "improve_pct": round(improve, 2),
            "gap_vs_best_pct": round(gap_best, 2) if best else "",
            "bound": res["bound"],
            "gap_to_bound_pct": round(gap_lb, 2),
            "time_limit": limit,
            "runtime_s": res["runtime"],
            "verified": "yes",
        })
        print("%-6s %5d %6d %8d %9d %6s %8.1f%% %8s %8.2f" %
              (name, n_ops, n_mach, base_mk, mk, res["status"][:6], improve,
               ("%.1f%%" % gap_best) if best else "-", res["runtime"]))

    if rows:
        with out_csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("-" * 78)
        print("写好了 %d 行 -> %s" % (len(rows), out_csv))
        print("注意：每行 verified=yes 才说明 plan 通过了四项校验，可以直接写进报告。")
    return 0


if __name__ == "__main__":
    sys.exit(main())