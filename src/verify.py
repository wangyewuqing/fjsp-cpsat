"""对任意排产结果做四项硬校验。

这一步的意义：只要机器会跑，就会有人（包括你自己）在报告里写一个错的 makespan。
校验脚本是唯一能证明「这个数不是编的」的东西，面试官问起来直接跑给他看。

四项校验：
    1 工序数必须等于算例总工序数（没漏排、没重复排）
    2 每道工序用的机器必须在它的可选机器集合里，且实际时长等于该机器的工时
    3 同一工件的工序必须按工艺顺序，后一道的开始 >= 前一道的结束
    4 同一台机器上任意两道工序的区间不能重叠
"""


def verify_plan(jobs, n_mach, plan):
    """通过则返回 makespan；不通过抛 AssertionError，消息里带具体位置。"""
    total = sum(len(j) for j in jobs)
    if len(plan) != total:
        raise AssertionError("工序数不对：排了 %d 道，应有 %d 道" % (len(plan), total))

    cnt = [0] * len(jobs)                       # 每个工件已出现几道工序
    per_job = [[] for _ in jobs]
    per_mach = [[] for _ in range(n_mach)]

    for j, m, st, fin in plan:
        o = cnt[j]
        if o >= len(jobs[j]):
            raise AssertionError("工件%d 被排了 %d 道，超过 %d 道" % (j, o + 1, len(jobs[j])))
        opts = dict(jobs[j][o])
        if m not in opts:
            raise AssertionError("工件%d 工序%d 用了不可选机器 %d（可选：%s）"
                                 % (j, o + 1, m, sorted(opts)))
        if fin - st != opts[m]:
            raise AssertionError("工件%d 工序%d 时长 %d != 工时 %d"
                                 % (j, o + 1, fin - st, opts[m]))
        if st < 0:
            raise AssertionError("工件%d 工序%d 开始时间为负" % (j, o + 1))
        cnt[j] += 1
        per_job[j].append((st, fin, o))
        per_mach[m].append((st, fin, j, o))

    # 3 工艺顺序
    for j, seq in enumerate(per_job):
        seq.sort()
        for a, b in zip(seq, seq[1:]):
            if b[0] < a[1]:
                raise AssertionError("工件%d 顺序冲突：工序%d 结束 %d > 工序%d 开始 %d"
                                     % (j, a[2] + 1, a[1], b[2] + 1, b[0]))

    # 4 机器互斥
    for m, seq in enumerate(per_mach):
        seq.sort()
        for a, b in zip(seq, seq[1:]):
            if b[0] < a[1]:
                raise AssertionError("机器%d 上重叠：工件%d工序%d[%d,%d) 与 工件%d工序%d[%d,%d)"
                                     % (m, a[2], a[3] + 1, a[0], a[1],
                                        b[2], b[3] + 1, b[0], b[1]))

    return max(f for seq in per_job for _, f, _ in seq)


if __name__ == "__main__":
    import sys
    from .fjsp_parser import load_brandimarte
    from src.baseline import list_schedule

    path = sys.argv[1] if len(sys.argv) > 1 else "data/mk01.txt"
    jobs, n_mach = load_brandimarte(path)
    mk, plan = list_schedule(jobs, n_mach)
    span = verify_plan(jobs, n_mach, plan)
    print("%s: 四项校验全部通过  makespan = %d（重算 %d）" % (path, mk, span))