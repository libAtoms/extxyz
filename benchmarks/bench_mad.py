"""Reproduce the chemfiles-author MAD benchmark and quantify the
regex -> whitespace-tokenizer speedup for our C parser.

Usage: python benchmarks/bench_mad.py [path-to-mad-train.xyz] [n_iter]
"""
import sys
import time

import ase.io
import ase_extxyz.io  # noqa: F401  registers format='cextxyz'
from chemfiles import Trajectory

filename = sys.argv[1] if len(sys.argv) > 1 else "mad-train.xyz"
n_iter = int(sys.argv[2]) if len(sys.argv) > 2 else 3


def best_of(fn, n):
    best = float("inf")
    last = None
    for _ in range(n):
        t0 = time.perf_counter()
        last = fn()
        dt = time.perf_counter() - t0
        best = min(best, dt)
    return best, last


def read_chemfiles():
    traj = Trajectory(filename)
    frames = [traj.read_step(i) for i in range(traj.nsteps)]
    return frames


# warm FS cache
n0 = len(ase.io.read(filename, format="cextxyz", index=":"))
print(f"frames: {n0}\n")

configs = [
    ("cextxyz (tokenizer, use_regex=False)",
     lambda: ase.io.read(filename, format="cextxyz", index=":", use_regex=False)),
    ("cextxyz (regex,     use_regex=True )",
     lambda: ase.io.read(filename, format="cextxyz", index=":", use_regex=True)),
    ("extxyz  (ASE built-in)",
     lambda: ase.io.read(filename, format="extxyz", index=":")),
    ("chemfiles",
     read_chemfiles),
]

results = {}
for name, fn in configs:
    dt, out = best_of(fn, n_iter)
    results[name] = dt
    print(f"{name:42s} {dt:6.2f}s  ({len(out)} frames)")

print()
tok = results["cextxyz (tokenizer, use_regex=False)"]
rgx = results["cextxyz (regex,     use_regex=True )"]
print(f"our tokenizer vs our regex:  {rgx/tok:.2f}x faster "
      f"({rgx:.2f}s -> {tok:.2f}s)")
print(f"our tokenizer vs ASE builtin: "
      f"{results['extxyz  (ASE built-in)']/tok:.2f}x faster")
print(f"chemfiles vs our tokenizer:  {tok/results['chemfiles']:.2f}x faster")
