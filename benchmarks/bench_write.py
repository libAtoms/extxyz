"""Benchmark: extxyz writers vs ASE built-in and the Rust extxyz-ng.

Mirrors ``bench_read.py``. Generates synthetic frames, then times writing each
with:

* ``extxyz.write_dicts(use_cextxyz=True)``  — this repo's C writer
* ``extxyz.write_dicts(use_cextxyz=False)`` — the pure-Python (np.savetxt) writer
* ``ase.io.write(format='extxyz')``         — ASE's built-in writer (baseline)
* ``ase.io.write(format='cextxyz')``        — the ase-extxyz plugin
* ``extxyz-ng`` ``write_frame``             — the Rust port, if ``EXTXYZ_NG_PYTHON``
  points at a venv that has it (run in a subprocess, like ``test_bench_vs_rust``).

Run::

    python benchmarks/bench_write.py [--max-atoms 200000] [--repeats 5]
    EXTXYZ_NG_PYTHON=/path/to/ng/bin/python python benchmarks/bench_write.py
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import numpy as np
import ase.io

import extxyz
import ase_extxyz.io  # noqa: F401  (registers the 'cextxyz' format)

from bench_read import make_xyz   # reuse the fixture generator


def _best(fn, repeats):
    best = float('inf')
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def _time_ng(src_path, repeats):
    """Time extxyz-ng's write_frame in its own interpreter (read a frame from
    ``src_path``, then time writing it). Returns ms or None if unavailable."""
    ng = os.environ.get('EXTXYZ_NG_PYTHON')
    if not ng:
        return None
    snippet = textwrap.dedent(f"""
        import time, tempfile, os, extxyz
        frame = extxyz.read_frame_from_file({str(src_path)!r})
        out = tempfile.mktemp(suffix='.xyz')
        def run():
            with open(out, 'wb') as fh:
                extxyz.write_frame(fh, frame)
        run()
        best = None
        for _ in range({repeats}):
            t0 = time.perf_counter(); run(); dt = time.perf_counter()-t0
            best = dt if best is None else min(best, dt)
        os.path.exists(out) and os.remove(out)
        print(best)
    """)
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    out = subprocess.run([ng, '-c', snippet], env=env,
                         capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        return None
    return float(out.stdout.strip().splitlines()[-1]) * 1e3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-atoms', type=int, default=200_000)
    ap.add_argument('--repeats', type=int, default=5)
    args = ap.parse_args()

    sizes = [n for n in (1000, 4000, 16000, 64000, args.max_atoms) if n <= args.max_atoms]

    hdr = (f'{"N atoms":>9}  {"MB":>6}  {"our C":>8}  {"pyPython":>9}  '
           f'{"ASE":>8}  {"plugin":>8}  {"ng":>8}  {"vs ASE":>7}  {"vs ng":>6}')
    print(hdr); print('-' * len(hdr))

    with tempfile.TemporaryDirectory() as tmp:
        for n in sizes:
            src = Path(tmp) / f'src_{n}.xyz'
            mb = make_xyz(src, n) / 1e6
            frames = extxyz.read_dicts(str(src))
            frames = frames if isinstance(frames, list) else [frames]
            atoms = ase.io.read(str(src), format='cextxyz', index=':')
            out = Path(tmp) / 'out.xyz'

            t_c = _best(lambda: extxyz.write_dicts(str(out), frames, use_cextxyz=True), args.repeats)
            t_py = _best(lambda: extxyz.write_dicts(str(out), frames, use_cextxyz=False), args.repeats)
            t_ase = _best(lambda: ase.io.write(str(out), atoms, format='extxyz'), args.repeats)
            t_plug = _best(lambda: ase.io.write(str(out), atoms, format='cextxyz'), args.repeats)
            t_ng = _time_ng(src, args.repeats)

            ng_s = f'{t_ng*1e3:8.1f}' if t_ng else f'{"n/a":>8}'
            vs_ng = f'{t_ng*1e3/(t_c*1e3):6.2f}x' if t_ng else f'{"-":>6}'
            print(f'{n:>9}  {mb:>6.2f}  {t_c*1e3:>8.1f}  {t_py*1e3:>9.1f}  '
                  f'{t_ase*1e3:>8.1f}  {t_plug*1e3:>8.1f}  {ng_s}  '
                  f'{t_ase/t_c:>6.2f}x  {vs_ng}')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
