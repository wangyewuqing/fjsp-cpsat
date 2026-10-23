"""最早完工派工（近似 SPT）：不给全局最优，只给一个能跑、可对比的锚点。"""
import sys

from .fjsp_parser import load_brandimarte


def list_schedule(jobs, n_mach):
    nxt = [0] * len(jobs)
    job_rdy = [0] * len(jobs)
    mch_rdy = [0] * n_mach
    plan, mk = [], 0
    for _ in range(sum(len(j) for j in jobs)):
        best = None
        for j, ops in enumerate(jobs):
            if nxt[j] >= len(ops):
                continue
            for m, p in ops[nxt[j]]:
                st = max(job_rdy[j], mch_rdy[m])
                fin = st + p
                if best is None or fin < best[0]:
                    best = (fin, j, m, st)
        fin, j, m, st = best
        job_rdy[j] = mch_rdy[m] = fin
        nxt[j] += 1
        plan.append((j, m, st, fin))
        mk = max(mk, fin)
    return mk, plan


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/mk01.txt"
    jobs, n_mach = load_brandimarte(path)
    mk, plan = list_schedule(jobs, n_mach)
    print(f"{path}: makespan = {mk}  工序数 = {len(plan)}")