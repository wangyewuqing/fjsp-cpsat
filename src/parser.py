"""Brandimarte FJSP 算例解析器。用法：python src/parser.py data/mk01.txt"""
import pathlib
import sys


def load_brandimarte(path):
    """返回 (jobs, n_mach)。jobs[j][o] = [(机器下标, 工时), ...]"""
    tok = pathlib.Path(path).read_text(encoding="utf-8").split()
    it = iter(tok)
    n_jobs, n_mach, _ = int(next(it)), int(next(it)), int(next(it))
    jobs = []
    for _ in range(n_jobs):
        n_ops = int(next(it))
        ops = []
        for _ in range(n_ops):
            k = int(next(it))
            opts = []
            for _ in range(k):
                m = int(next(it)) - 1          # 1-based -> 0-based
                t = int(next(it))
                opts.append((m, t))
            ops.append(opts)
        jobs.append(ops)
    return jobs, n_mach


def check(jobs, n_mach):
    """三项校验 + 时间上界。任何一项不过直接抛异常。"""
    n_ops = sum(len(j) for j in jobs)
    for j, ops in enumerate(jobs):
        for o, opts in enumerate(ops):
            if not opts:
                raise ValueError(f"工件{j} 工序{o} 没有可选机器")
            for m, t in opts:
                if not (0 <= m < n_mach):
                    raise ValueError(f"机器号越界：工件{j} 工序{o} 机器{m}")
                if t <= 0:
                    raise ValueError(f"工时非正：工件{j} 工序{o}  t={t}")
    upper = sum(max(t for _, t in op) for job in jobs for op in job)
    return n_ops, upper


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/mk01.txt"
    jobs, n_mach = load_brandimarte(path)
    n_ops, upper = check(jobs, n_mach)
    print(f"{path}: 工件 {len(jobs)} / 机器 {n_mach} / 工序 {n_ops} / 时间上界 {upper}")
    for o, opts in enumerate(jobs[0]):
        print(f"  工件1 工序{o + 1}: {opts}")