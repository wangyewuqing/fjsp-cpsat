"""产品族换型矩阵：把「换型时间」这件事变成数据，而不是拍脑袋。

公开算例（Brandimarte MK01–MK10）不含换型数据，所以这里用一条明确、可复现的规则：

    每个工件属于一个「产品族」（默认 3 族）；
    同族之间切换 s = 0，跨族切换 s = 设定的换型时间；
    换型只发生在同一台机器上前后两道工序之间。

生成规则写进 data/README.md，报告里就能说清「这个 s 是怎么来的」，
而不是被人问一句「45 哪来的」就哑了。

用法：
    python src/setup_matrix.py                 # 打印默认 3 族、s=45 的矩阵
    python src/setup_matrix.py 4 60            # 4 族、跨族 60
    python src/setup_matrix.py 3 45 --save data/setup_matrix.csv
"""
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

DEFAULT_FAMILIES = 3
DEFAULT_SETUP = 45


def assign_families(n_jobs, k=DEFAULT_FAMILIES, seed=None):
    """按工件编号连续分族：前 1/k 的工件属于族 0，依此类推。

    seed 不为 None 时把族号打乱（模拟「订单混排」，同一个种子可复现）。
    """
    if k < 1:
        raise ValueError("族数至少要 1")
    fam = [min(k - 1, j * k // max(n_jobs, 1)) for j in range(n_jobs)]
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(fam)
    return fam


def build_matrix(k=DEFAULT_FAMILIES, s=DEFAULT_SETUP, symmetric=True):
    """k×k 换型矩阵：对角线 0，其余为 s。"""
    m = [[0 if a == b else s for b in range(k)] for a in range(k)]
    if not symmetric:
        rng = random.Random(0)
        for a in range(k):
            for b in range(k):
                if a != b:
                    m[a][b] = s + rng.randint(0, max(1, s // 3))
    return m


def save_matrix(path, matrix):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    k = len(matrix)
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write("," + ",".join("F%d" % b for b in range(k)) + "\n")
        for a in range(k):
            fh.write("F%d," % a + ",".join(str(matrix[a][b]) for b in range(k)) + "\n")
    return path


def load_matrix(path):
    lines = pathlib.Path(path).read_text(encoding="utf-8").strip().splitlines()
    rows = [ln.split(",")[1:] for ln in lines[1:]]
    return [[int(x) for x in row] for row in rows]


def setup_of(matrix, fa, fb):
    """从族 a 切到族 b 的换型时间（同一工件内不会发生换型，这里只处理跨工序）。"""
    return matrix[fa][fb]


def print_matrix(k, s):
    m = build_matrix(k, s)
    print("换型矩阵 %d 族，跨族 %d：" % (k, s))
    print("     " + "".join("%6s" % ("F%d" % b) for b in range(k)))
    for a in range(k):
        print("%4s " % ("F%d" % a) + "".join("%6d" % m[a][b] for b in range(k)))


if __name__ == "__main__":
    argv = sys.argv[1:]

    def _arg(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    if "--help" in argv or "-h" in argv:
        print(__doc__)
        sys.exit(0)

    k = int(_arg("--families", DEFAULT_FAMILIES))
    s_val = int(_arg("--setup", DEFAULT_SETUP))
    print_matrix(k, s_val)
    if "--save" in argv:
        out = _arg("--save", "data/setup_matrix.csv")
        print("已保存 ->", save_matrix(out, build_matrix(k, s_val)))
