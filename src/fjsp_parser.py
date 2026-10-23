"""Brandimarte FJSP 算例解析器。

用法：
    python src/parser.py data/mk01.txt

关于机器编号：Brandimarte 的算例在不同来源里编号基准不一致——
经典发行版是 1-based（机器号 1..m），有些 GitHub 复现仓库改成了 0-based（0..m-1）。
本解析器自动识别每个文件的基准，不需要你手动改代码。
"""
import pathlib
import sys


def _parse_raw(tok):
    """先按原值读出机器号，不做任何偏移。"""
    it = iter(tok)
    n_jobs = int(next(it))
    n_mach = int(next(it))
    next(it)                                    # 第三个数字（平均工序数等）不用
    raw = []
    for _ in range(n_jobs):
        n_ops = int(next(it))
        ops = []
        for _ in range(n_ops):
            k = int(next(it))
            opts = []
            for _ in range(k):
                m = int(next(it))
                t = int(next(it))
                opts.append((m, t))
            ops.append(opts)
        raw.append(ops)
    return raw, n_mach


def detect_base(raw, n_mach):
    """判断机器号是 0-based 还是 1-based，返回 0 或 1。"""
    ms = [m for job in raw for op in job for m, _ in op]
    lo, hi = min(ms), max(ms)
    if lo == 0:                 # 出现 0，只能是 0-based
        return 0
    if hi == n_mach:            # 出现 m，说明 1..m，是 1-based
        return 1
    if hi == n_mach - 1:        # 最大只到 m-1，是 0-based
        return 0
    return 1 if lo == 1 else 0


def load_with_base(path):
    """返回 (jobs, n_mach, base)。jobs[j][o] = [(机器下标, 工时), ...]，下标从 0 开始。"""
    text = pathlib.Path(path).read_text(encoding="utf-8-sig")
    raw, n_mach = _parse_raw(text.split())
    base = detect_base(raw, n_mach)
    jobs = [[[(m - base, t) for m, t in op] for op in job] for job in raw]
    return jobs, n_mach, base


def load_brandimarte(path):
    """只要 (jobs, n_mach)，兼容旧调用。"""
    jobs, n_mach, _ = load_with_base(path)
    return jobs, n_mach


def check(jobs, n_mach):
    """三项校验 + 时间上界。任何一项不过直接抛异常。"""
    n_ops = sum(len(j) for j in jobs)
    if n_ops == 0:
        raise ValueError("一道工序都没解析出来，检查文件格式")
    for j, ops in enumerate(jobs):
        for o, opts in enumerate(ops):
            if not opts:
                raise ValueError("工件%d 工序%d 没有可选机器" % (j, o))
            for m, t in opts:
                if not (0 <= m < n_mach):
                    raise ValueError("机器号越界：工件%d 工序%d 机器%d" % (j, o, m))
                if t <= 0:
                    raise ValueError("工时非正：工件%d 工序%d t=%d" % (j, o, t))
    upper = sum(max(t for _, t in op) for job in jobs for op in job)
    return n_ops, upper


def summarize(path):
    """一次拿到全部摘要信息：jobs, n_mach, n_ops, upper, base。"""
    jobs, n_mach, base = load_with_base(path)
    n_ops, upper = check(jobs, n_mach)
    return jobs, n_mach, n_ops, upper, base


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/mk01.txt"
    jobs, n_mach, n_ops, upper, base = summarize(path)
    print("%s: 工件 %d / 机器 %d / 工序 %d / 时间上界 %d / 机器基准 %d-based"
          % (path, len(jobs), n_mach, n_ops, upper, base))
    for o, opts in enumerate(jobs[0]):
        print("  工件1 工序%d: %s" % (o + 1, opts))