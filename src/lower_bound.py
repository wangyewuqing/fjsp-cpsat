"""makespan 的简易下界（LB）。

「比最好解差 42%」说明不了你的解有多差——最好解是别人花几个月调出来的。
「比理论下界高 2.1 倍」才说明你的方法本身离极限有多远，而且这个下界不依赖任何论文数据，
面试官自己也能推出来，可信度更高。

两个都是严格下界：
    LB_job = max_j Σ_o min_m t(j,o,m)        每个工件自己的最长链（工序串行，不可能更快）
    LB_mch = ceil( Σ_(j,o) min_m t(j,o,m) / m )  总工作量摊到 m 台机器上
取两者较大的那个。
"""
from math import ceil


def lower_bound(jobs, n_mach):
    """返回 (LB, LB_job, LB_mch)。"""
    per_job = []
    total = 0
    for job in jobs:
        s = 0
        for op in job:
            m = min(t for _, t in op)
            s += m
            total += m
        per_job.append(s)
    lb_job = max(per_job) if per_job else 0
    lb_mch = ceil(total / n_mach)
    return max(lb_job, lb_mch), lb_job, lb_mch


if __name__ == "__main__":
    import sys
    from parser import load_brandimarte

    path = sys.argv[1] if len(sys.argv) > 1 else "data/mk01.txt"
    jobs, n_mach = load_brandimarte(path)
    lb, a, b = lower_bound(jobs, n_mach)
    print("%s: LB = %d  (工件链 %d / 机器容量 %d)" % (path, lb, a, b))