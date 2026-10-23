"""Brandimarte FJSP 算例解析器。

用法：
    python src/parser.py data/mk01.txt
"""
import pathlib
import sys


def load_brandimarte(path):
    """解析一个 Brandimarte 格式的算例。

    返回 (jobs, n_mach)：
        jobs[j][o] = [(机器下标, 工时), ...]   机器下标从 0 开始
    文件格式（纯文本，全是一串数字）：
        第 1 行   工件数 机器数 (第三个数字各版本含义不同，直接跳过)
        每个工件：工序数
        每道工序：可选机器数 k，随后 k 组 (机器号, 工时)
    """
    tok = pathlib.Path(path).read_text(encoding="utf-8-sig").split()
    it = iter(tok)
    n_jobs = int(next(it))
    n_mach = int(next(it))
    next(it)                                    # 第三个数字不用
    jobs = []
    for _ in range(n_jobs):
        n_ops = int(next(it))
        ops = []
        for _ in range(n_ops):
            k = int(next(it))
            opts = []
            for _ in range(k):
                m = int(next(it)) - 1           # 1-based -> 0-based
                t = int(next(it))
                opts.append((m, t))
            ops.append(opts)
        jobs.append(ops)
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
    jobs, n_mach = load_brandimarte(path)
    n_ops, upper = check(jobs, n_mach)
    return jobs, n_mach, n_ops, upper


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/mk01.txt"
    jobs, n_mach, n_ops, upper = summarize(path)
    print("%s: 工件 %d / 机器 %d / 工序 %d / 时间上界 %d"
          % (path, len(jobs), n_mach, n_ops, upper))
    for o, opts in enumerate(jobs[0]):
        print("  工件1 工序%d: %s" % (o + 1, opts))