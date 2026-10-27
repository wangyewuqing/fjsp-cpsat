"""把 baseline.csv 和 cpsat.csv 合并成一张总表，顺手生成 markdown 版（直接贴报告/README）。

用法（在仓库根目录）：
    python benchmark/make_summary.py
    python benchmark/make_summary.py --baseline results/baseline.csv --cpsat results/cpsat.csv

输出：
    results/summary.csv   机器可读的总表
    results/summary.md    markdown 表格 + 结论段，可直接贴进 report/README.md
"""
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def read_csv(path):
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return {row["instance"]: row for row in csv.DictReader(fh)}


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    argv = sys.argv[1:]

    def arg(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    base = read_csv(arg("--baseline", "results/baseline.csv"))
    cp = read_csv(arg("--cpsat", "results/cpsat.csv"))
    out_csv = pathlib.Path(arg("--out", "results/summary.csv"))
    out_md = pathlib.Path(arg("--md", "results/summary.md"))

    if not base:
        print("没有 baseline 结果，先跑 python benchmark/run_all.py")
        return 1

    rows = []
    for name in sorted(base):
        b = base[name]
        c = cp.get(name, {})
        baseline_mk = to_float(b.get("makespan"))
        cpsat_mk = to_float(c.get("cpsat"))
        rows.append({
            "instance": name,
            "jobs": b.get("jobs", ""),
            "machines": b.get("machines", ""),
            "ops": b.get("ops", ""),
            "best_known": b.get("best_known", ""),
            "baseline_makespan": b.get("makespan", ""),
            "baseline_gap_pct": b.get("gap_pct", ""),
            "cpsat_makespan": c.get("cpsat", ""),
            "cpsat_status": c.get("status", ""),
            "cpsat_improve_pct": c.get("improve_pct", ""),
            "cpsat_gap_vs_best_pct": c.get("gap_vs_best_pct", ""),
            "lower_bound": b.get("lower_bound", ""),
            "mk_over_lb": b.get("mk_over_lb", ""),
            "baseline_verified": b.get("verified", ""),
            "cpsat_verified": c.get("verified", ""),
        })

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("写好了 %d 行 -> %s" % (len(rows), out_csv))

    # ---- markdown ----
    lines = []
    lines.append("| 算例 | 工件×机器 | 工序 | 派工 makespan | 派工 gap | CP-SAT makespan | 改善 | CP-SAT gap | 校验 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        bmk = to_float(r["baseline_makespan"])
        cmk = to_float(r["cpsat_makespan"])
        gap_b = to_float(r["baseline_gap_pct"])
        gap_c = to_float(r["cpsat_gap_vs_best_pct"])
        imp = to_float(r["cpsat_improve_pct"])
        ok = r["cpsat_verified"] == "yes"
        lines.append("| %s | %s×%s | %s | %d | %+.1f%% | %s | %s | %s | %s |" % (
            r["instance"], r["jobs"], r["machines"], r["ops"], bmk,
            gap_b if gap_b is not None else 0.0,
            "%d" % cmk if cmk is not None else "-",
            "%+.1f%%" % imp if imp is not None else "-",
            "%+.1f%%" % gap_c if gap_c is not None else "-",
            "✓" if ok else "—",
        ))
    lines.append("")
    lines.append("> 校验 = 四项校验（工序全覆盖 / 不重叠 / 前置顺序 / makespan 复算一致）全过。")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("写好了 markdown -> %s" % out_md)

    # ---- 结论段 ----
    gaps_b = [to_float(r["baseline_gap_pct"]) for r in rows if to_float(r["baseline_gap_pct"]) is not None]
    imps = [to_float(r["cpsat_improve_pct"]) for r in rows if to_float(r["cpsat_improve_pct"]) is not None]
    if gaps_b:
        print("派工基线 gap 区间 %.1f%%–%.1f%%，平均 %.1f%%（%d 个算例）"
              % (min(gaps_b), max(gaps_b), sum(gaps_b) / len(gaps_b), len(gaps_b)))
    if imps:
        print("CP-SAT 相对派工的改善区间 %.1f%%–%.1f%%，平均 %.1f%%（%d 个算例）"
              % (min(imps), max(imps), sum(imps) / len(imps), len(imps)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
