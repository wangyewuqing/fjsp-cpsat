"""换型实验：同一算例，在「假设换型为 0」与「含换型」之间对比，并对换型时间做敏感性分析。

流程：
    阶段一  无换型 CP-SAT → 得到机器指派与基准 makespan
    阶段二  机器固定，AddCircuit 排序列 + 弧上加换型时间 → 含换型 makespan
    敏感性  对多个 s 重复阶段二，看 makespan 怎么涨

用法（在仓库根目录）：
    python benchmark/run_setup.py --instances mk01,mk05 --setups 15,45,90
    python benchmark/run_setup.py --instances mk01 --alpha 0.5,1,2,4
    python benchmark/run_setup.py --instances mk01,mk05 --setups 15,45,90 --limit 120
"""
import csv
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.fjsp_parser import summarize                       # noqa: E402
from src.verify import verify_plan                          # noqa: E402
from src.model_cpsat import solve as solve_phase1           # noqa: E402
from src.model_setup import assign_from_plan, solve_phase2  # noqa: E402
from src.setup_matrix import (                              # noqa: E402
    assign_families, build_matrix, save_matrix,
)


def write_rows(rows, out_csv):
    fields = list(rows[0].keys())

    def _write(path):
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write(out_csv)
        print("写好了 %d 行 -> %s" % (len(rows), out_csv))
        return out_csv
    except PermissionError:
        alt = out_csv.with_name("%s_%s%s" % (out_csv.stem, time.strftime("%Y%m%d_%H%M"), out_csv.suffix))
        _write(alt)
        print("!! %s 被占用，结果已改写到：%s" % (out_csv, alt))
        return alt


def mean_op_time(jobs):
    vals = [min(t for _, t in op) for job in jobs for op in job]
    return sum(vals) / len(vals)


def main():
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    print("== run_setup.py：换型两阶段对比（阶段一无换型 / 阶段二 AddCircuit 加换型）==")

    def arg(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    data_dir = pathlib.Path(arg("--data", "data"))
    names = [s.strip() for s in arg("--instances", "mk01,mk05").split(",") if s.strip()]
    limit = float(arg("--limit", "60"))
    k_fam = int(arg("--families", "3"))
    setups = [int(x) for x in arg("--setups", "15,45,90").split(",") if x.strip()]
    alphas = [float(x) for x in arg("--alpha", "").split(",") if x.strip()]
    seed = int(arg("--seed", "0"))
    workers = int(arg("--workers", "8"))
    fam_seed = arg("--family-seed", "")
    out_csv = pathlib.Path(arg("--out", "results/setup.csv"))

    fam_seed = int(fam_seed) if fam_seed != "" else None

    rows = []
    for name in names:
        f = data_dir / (name + ".txt")
        if not f.exists():
            print("%-6s 跳过：找不到 %s" % (name, f))
            continue
        jobs, n_mach, n_ops, _, _base = summarize(f)
        families = assign_families(len(jobs), k_fam, seed=fam_seed)
        mp = mean_op_time(jobs)

        p1 = solve_phase1(jobs, n_mach, time_limit=limit, seed=seed, workers=workers)
        if not p1["plan"]:
            print("%-6s 阶段一无所获：%s" % (name, p1["status"]))
            continue
        verify_plan(jobs, n_mach, p1["plan"])
        assign = assign_from_plan(jobs, p1["plan"])
        mk0 = p1["makespan"]

        # 敏感性档位：绝对 s，或按平均工时归一化的 alpha
        levels = [("s=%d" % s, s) for s in setups]
        for a in alphas:
            levels.append((("alpha=%.1f" % a), max(1, int(round(a * mp)))))

        print("\n%s: 工序 %d / 机器 %d / 无换型 makespan = %d（%s）/ 平均工时 %.1f"
              % (name, n_ops, n_mach, mk0, p1["status"], mp))
        print("  %-12s %9s %9s %8s %9s %8s" %
              ("换型设定", "makespan", "换型总量", "涨幅", "s/平均工时", "用时s"))
        print("  " + "-" * 62)

        for label, s in levels:
            matrix = build_matrix(k_fam, s)
            t0 = time.perf_counter()
            p2 = solve_phase2(jobs, n_mach, assign, families, matrix,
                              time_limit=limit, seed=seed, workers=workers,
                              hint_plan=p1["plan"])
            rt = time.perf_counter() - t0
            if not p2["plan"]:
                print("  %-12s 无解：%s" % (label, p2["status"]))
                continue
            verify_plan(jobs, n_mach, p2["plan"])
            inc = (p2["makespan"] - mk0) * 100.0 / mk0
            rows.append({
                "instance": name,
                "ops": n_ops,
                "machines": n_mach,
                "families": k_fam,
                "setup_time": s,
                "mean_op_time": round(mp, 2),
                "setup_over_mean": round(s / mp, 2),
                "makespan_no_setup": mk0,
                "makespan_setup": p2["makespan"],
                "increase_pct": round(inc, 2),
                "total_setup_time": p2["total_setup"],
                "status": p2["status"],
                "runtime_s": round(rt, 2),
                "verified": "yes",
            })
            print("  %-12s %9d %9d %7.1f%% %9.2f %8.2f"
                  % (label, p2["makespan"], p2["total_setup"], inc, s / mp, rt))

    if not rows:
        print("\n没有产出任何一行，检查 --instances 与 data 目录")
        return 1

    out = write_rows(rows, out_csv)
    mx = data_dir / ("setup_matrix_%dfam.csv" % k_fam)
    save_matrix(mx, build_matrix(k_fam, setups[0] if setups else 45))
    print("换型矩阵已保存：%s（和算例放在一起，报告里要说明它是怎么生成的）" % mx)
    print("注意：每行 verified=yes 说明计划通过了四项结构校验；换型只影响时间，不影响可行性。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
