"""Paired 18-seed comparison for the storage-limit / volunteer-release fix.

    python tools/food_storage_eval/run_compare.py <out_dir> [--seeds 11-28] [--workers 14] [--variants A,F0,C4,Dprev,D]

Builds three source trees in <out_dir>/trees:
  committed  git archive 32c1478 (the baseline revision)
  candidate  the current working tree's tiandao/
  previous   the candidate with tiandao/food.py replaced by previous_rule_food.py (release at the local limit)
then runs balance_run.py once per (variant, seed) in its own process and writes <out_dir>/<variant>_<seed>.json.
Variants: A = committed; F0, C4 = candidate with features switched off by variant.py; Dprev = previous rule; D = candidate.
"""
import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BASELINE = "32c147809b80927480c663d72bd5a2ea42b15f62"


def build_trees(out):
    trees = os.path.join(out, "trees")
    committed, candidate, previous = (os.path.join(trees, n) for n in ("committed", "candidate", "previous"))
    if not os.path.isdir(committed):
        os.makedirs(committed)
        archive = subprocess.run(["git", "-C", REPO, "archive", BASELINE, "tiandao"], check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", committed], input=archive, check=True)
    for dest in (candidate, previous):
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(os.path.join(REPO, "tiandao"), os.path.join(dest, "tiandao"),
                        ignore=shutil.ignore_patterns("__pycache__", "world.save*", "backups", "archive", "*.jsonl"))
    shutil.copyfile(os.path.join(HERE, "previous_rule_food.py"), os.path.join(previous, "tiandao", "food.py"))
    return {"A": (committed, "A"), "F0": (candidate, "F0"), "C4": (candidate, "C4"),
            "Dprev": (previous, "D"), "D": (candidate, "D")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seeds", default="11-28")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--variants", default="A,F0,C4,Dprev,D")
    args = ap.parse_args()
    lo, hi = (int(x) for x in args.seeds.split("-"))
    os.makedirs(args.out, exist_ok=True)
    repos = build_trees(args.out)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    jobs = [(v, s) for s in range(lo, hi + 1) for v in args.variants.split(",")]

    def run(job):
        v, s = job
        repo, var = repos[v]
        with open(os.path.join(args.out, f"{v}_{s}.json"), "w") as out, \
                open(os.path.join(args.out, f"{v}_{s}.err"), "w") as err:
            return subprocess.call([sys.executable, os.path.join(HERE, "balance_run.py"), repo, str(s), var],
                                   stdout=out, stderr=err, env=env)

    with ThreadPoolExecutor(args.workers) as pool:
        codes = list(pool.map(run, jobs))
    failed = [j for j, c in zip(jobs, codes) if c]
    print("failed:", failed)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
