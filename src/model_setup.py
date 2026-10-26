"""两阶段求解：先定机器，再在每台机器上排顺序并插入换型时间。

为什么不能一次解：
    sequence-dependent setup 让「机器上的顺序」本身变成变量，
    相邻两道工序之间要加一段取决于「上一个是谁」的时间。
    一次解需要 O(n²) 条弧的 AddCircuit，规模一大直接爆掉。

两阶段的取舍（写进报告的那句话）：
    牺牲全局最优性，换来可解、可解释、可讲；
    报告里要给出「相比一次解损失多少」的估计。

实现要点：
    第一阶段  沿用 model_cpsat.solve 得到「每道工序在哪台机器」；
    第二阶段  机器固定后，每台机器上的工序串成一个环（哑节点做起点/终点），
              弧上带换型时间：选中 i→j 时 start[j] >= end[i] + setup(fam_i, fam_j)。
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ortools.sat.python import cp_model  # noqa: E402

from setup_matrix import setup_of  # noqa: E402

STATUS_NAME = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


def assign_from_plan(jobs, plan):
    """把 [(工件, 机器, 开始, 结束), ...] 还原成 {(工件, 工序): 机器}。"""
    cnt = [0] * len(jobs)
    assign = {}
    for j, m, _st, _fin in plan:
        o = cnt[j]
        cnt[j] += 1
        assign[(j, o)] = m
    for j, job in enumerate(jobs):
        if cnt[j] != len(job):
            raise ValueError("工件%d 的计划工序数 %d != %d" % (j, cnt[j], len(job)))
    return assign


def plan_setups(jobs, families, matrix, plan):
    """统计每台机器上相邻工序之间的换型总时间。"""
    per_mach = {}
    for j, m, st, fin in plan:
        per_mach.setdefault(m, []).append((st, j))
    total = 0
    detail = []
    for m, seq in per_mach.items():
        seq.sort()
        for (_, j0), (_, j1) in zip(seq, seq[1:]):
            s = setup_of(matrix, families[j0], families[j1])
            if s:
                total += s
                detail.append((m, j0, j1, s))
    return total, detail


def solve_phase2(jobs, n_mach, assign, families, matrix,
                 time_limit=60.0, seed=0, workers=8, hint_plan=None):
    """机器固定后求序列与开始时间。返回 dict(status/makespan/plan/total_setup/runtime)。"""
    mdl = cp_model.CpModel()

    dur = {}
    for j, job in enumerate(jobs):
        for o, opts in enumerate(job):
            dur[j, o] = dict(opts)[assign[j, o]]

    max_setup = max(max(row) for row in matrix) if matrix else 0
    horizon = sum(dur.values()) + len(dur) * max_setup

    start, end = {}, {}
    for (j, o), d in dur.items():
        start[j, o] = mdl.NewIntVar(0, horizon, "s_%d_%d" % (j, o))
        end[j, o] = mdl.NewIntVar(0, horizon, "e_%d_%d" % (j, o))
        mdl.Add(end[j, o] == start[j, o] + d)

    # 同一工件：工艺顺序
    for j, job in enumerate(jobs):
        for o in range(len(job) - 1):
            mdl.Add(start[j, o + 1] >= end[j, o])

    # 每台机器：工序 + 哑节点 串成一个环
    per_mach = {}
    for (j, o), m in assign.items():
        per_mach.setdefault(m, []).append((j, o))

    for m, ops in per_mach.items():
        if not ops:
            continue
        dummy = (-1, -1)
        nodes = list(ops) + [dummy]
        idx = {nd: i for i, nd in enumerate(nodes)}
        arcs = []
        for a in nodes:
            for b in nodes:
                if a == b:
                    continue
                lit = mdl.NewBoolVar("a_%d_%d_%d" % (m, idx[a], idx[b]))
                arcs.append((idx[a], idx[b], lit))
                if a == dummy or b == dummy:
                    continue
                st = setup_of(matrix, families[a[0]], families[b[0]])
                if st:
                    mdl.Add(start[b[0], b[1]] >= end[a[0], a[1]] + st).OnlyEnforceIf(lit)
                else:
                    mdl.Add(start[b[0], b[1]] >= end[a[0], a[1]]).OnlyEnforceIf(lit)
        mdl.AddCircuit(arcs)

    makespan = mdl.NewIntVar(0, horizon, "makespan")
    mdl.AddMaxEquality(makespan, [end[j, len(job) - 1] for j, job in enumerate(jobs)])
    mdl.Minimize(makespan)

    if hint_plan:
        cnt = [0] * len(jobs)
        for j, _m, st, _fin in hint_plan:
            o = cnt[j]
            cnt[j] += 1
            mdl.AddHint(start[j, o], int(st))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = workers if workers else 0
    solver.parameters.random_seed = seed
    status = solver.Solve(mdl)

    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    plan = []
    if ok:
        for j, job in enumerate(jobs):
            for o in range(len(job)):
                s = solver.Value(start[j, o])
                plan.append((j, assign[j, o], s, s + dur[j, o]))
    total_setup, detail = plan_setups(jobs, families, matrix, plan) if ok else (0, [])
    return {
        "status": STATUS_NAME.get(status, str(status)),
        "makespan": int(solver.ObjectiveValue()) if ok else None,
        "bound": int(solver.BestObjectiveBound()) if ok else None,
        "plan": plan,
        "total_setup": total_setup,
        "setup_detail": detail,
        "runtime": round(solver.WallTime(), 2),
    }


if __name__ == "__main__":
    import time

    from baseline import list_schedule
    from fjsp_parser import load_brandimarte
    from model_cpsat import solve as solve_phase1
    from setup_matrix import assign_families, build_matrix
    from verify import verify_plan

    path = sys.argv[1] if len(sys.argv) > 1 else "data/mk01.txt"
    s = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    jobs, n_mach = load_brandimarte(path)
    families = assign_families(len(jobs), k)
    matrix = build_matrix(k, s)

    t0 = time.perf_counter()
    p1 = solve_phase1(jobs, n_mach, time_limit=60)
    t1 = time.perf_counter() - t0
    assert p1["plan"], "第一阶段没解出来"
    verify_plan(jobs, n_mach, p1["plan"])
    print("阶段一（无换型）: %s  makespan = %d  用时 %.2fs" % (p1["status"], p1["makespan"], t1))

    assign = assign_from_plan(jobs, p1["plan"])
    t0 = time.perf_counter()
    p2 = solve_phase2(jobs, n_mach, assign, families, matrix, time_limit=60, hint_plan=p1["plan"])
    t2 = time.perf_counter() - t0
    if not p2["plan"]:
        print("阶段二没解出来:", p2["status"])
        sys.exit(1)
    verify_plan(jobs, n_mach, p2["plan"])
    print("阶段二（含换型 s=%d, %d 族）: %s  makespan = %d  换型总量 %d  用时 %.2fs"
          % (s, k, p2["status"], p2["makespan"], p2["total_setup"], t2))
    print("makespan 上涨 %.1f%%（%.2f → %.2f）"
          % ((p2["makespan"] - p1["makespan"]) * 100.0 / p1["makespan"],
             p1["makespan"], p2["makespan"]))
    print("四项校验通过（换型只影响时间，不影响可行性）")