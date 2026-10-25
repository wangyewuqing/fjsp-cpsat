"""CP-SAT 求解 FJSP（无换型版本）。

建模要点（每一行都对应一个车间约束）：
    1  每道工序选一台机器           → AddExactlyOne(该工序所有机器选项)
    2  每道工序有开始/结束时间        → NewOptionalIntervalVar(start, p, end, lit)
    3  同一台机器上的工序不能重叠     → AddNoOverlap(该机器的所有区间)
    4  同一工件的工序必须按顺序       → start[o+1] >= end[o]
    5  目标：最小化最大完工时间       → AddMaxEquality(makespan, 所有 end)

用法：
    python src/model_cpsat.py data/mk01.txt 60
"""
import sys

from ortools.sat.python import cp_model

STATUS_NAME = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


def solve(jobs, n_mach, time_limit=60.0, seed=0, workers=8, hint_plan=None, log=False):
    """返回 dict：status / makespan / bound / plan / runtime。

    hint_plan: [(工件, 机器, 开始, 结束), ...]，通常传派工基线的结果，
               给求解器一个可行起点，小算例能快好几倍。
    """
    mdl = cp_model.CpModel()
    horizon = sum(max(t for _, t in op) for job in jobs for op in job)

    start, end = {}, {}
    choose = {}                     # (j, o, m) -> BoolVar
    per_mach = [[] for _ in range(n_mach)]
    all_ends = []

    for j, job in enumerate(jobs):
        for o, opts in enumerate(job):
            s = mdl.NewIntVar(0, horizon, "s_%d_%d" % (j, o))
            e = mdl.NewIntVar(0, horizon, "e_%d_%d" % (j, o))
            start[j, o], end[j, o] = s, e
            lits = []
            for m, p in opts:
                lit = mdl.NewBoolVar("x_%d_%d_%d" % (j, o, m))
                choose[j, o, m] = lit
                lits.append(lit)
                # 选中时 e = s + p；未选中时这条区间不参与 NoOverlap
                per_mach[m].append(
                    mdl.NewOptionalIntervalVar(s, p, e, lit, "iv_%d_%d_%d" % (j, o, m))
                )
            mdl.AddExactlyOne(lits)                  # 约束 1

    for m in range(n_mach):
        mdl.AddNoOverlap(per_mach[m])                # 约束 3

    for j, job in enumerate(jobs):
        for o in range(len(job) - 1):
            mdl.Add(start[j, o + 1] >= end[j, o])    # 约束 4
        all_ends.append(end[j, len(job) - 1])

    makespan = mdl.NewIntVar(0, horizon, "makespan")
    mdl.AddMaxEquality(makespan, [end[j, len(job) - 1] for j, job in enumerate(jobs)])
    mdl.Minimize(makespan)                           # 约束 5

    if hint_plan:
        add_hint(mdl, jobs, hint_plan, start, choose)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = workers if workers else 0
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = log
    status = solver.Solve(mdl)

    plan = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for j, job in enumerate(jobs):
            for o, opts in enumerate(job):
                for m, p in opts:
                    if solver.Value(choose[j, o, m]):
                        s = solver.Value(start[j, o])
                        plan.append((j, m, s, s + p))
                        break

    return {
        "status": STATUS_NAME.get(status, str(status)),
        "makespan": int(solver.ObjectiveValue()) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "bound": int(solver.BestObjectiveBound()) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "plan": plan,
        "runtime": round(solver.WallTime(), 2),
    }


def add_hint(mdl, jobs, plan, start, choose):
    """把一份可行解作为初始提示交给求解器（不影响正确性，只加速）。"""
    cnt = [0] * len(jobs)
    for j, m, st, fin in plan:
        o = cnt[j]
        cnt[j] += 1
        mdl.AddHint(start[j, o], int(st))
        for (mm, _p) in jobs[j][o]:
            key = (j, o, mm)
            if key in choose:
                mdl.AddHint(choose[key], 1 if mm == m else 0)


if __name__ == "__main__":
    from src.fjsp_parser import load_brandimarte
    from src.baseline import list_schedule
    from src.lower_bound import lower_bound
    from src.verify import verify_plan

    path = sys.argv[1] if len(sys.argv) > 1 else "data/mk01.txt"
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

    jobs, n_mach = load_brandimarte(path)
    lb, _, _ = lower_bound(jobs, n_mach)
    base_mk, base_plan = list_schedule(jobs, n_mach)

    print("%s: 工序 %d / 机器 %d / 下界 LB %d / 派工基线 %d"
          % (path, sum(len(j) for j in jobs), n_mach, lb, base_mk))
    print("求解中（上限 %.0f 秒）..." % limit)

    res = solve(jobs, n_mach, time_limit=limit, hint_plan=base_plan)
    if res["plan"]:
        span = verify_plan(jobs, n_mach, res["plan"])
        assert span == res["makespan"], "报表 %s 与重算 %s 不一致" % (res["makespan"], span)
        print("CP-SAT: %s  makespan = %d  下界 %d  gap = %.1f%%"
              % (res["status"], res["makespan"], res["bound"],
                 (res["makespan"] - res["bound"]) * 100.0 / res["bound"]))
        print("相对派工基线改善 %.1f%%，耗时 %.2f 秒"
              % ((base_mk - res["makespan"]) * 100.0 / base_mk, res["runtime"]))
        print("四项校验通过")
    else:
        print("没拿到可行解：%s" % res["status"])