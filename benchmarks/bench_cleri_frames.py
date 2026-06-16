"""Benchmark the comment-line parser: libcleri grammar (use_cleri=True, default)
vs the first-char dispatch parser (use_cleri=False).

The dispatch parser's win is on the PER-FRAME comment line, so it is amortised
away on single huge frames (see bench_read.py) and shows up on files with many
small frames. This sweeps atoms-per-frame at a fixed total atom count and times
the C reader both ways (per-atom tokenizer in both; only the comment parser
differs).

Run::

    python benchmarks/bench_cleri_frames.py [--total 1000000] [--repeats 3]
"""
from __future__ import annotations

import argparse
import csv
import sys
import tempfile
import time
from pathlib import Path

import ase.io
import ase_extxyz.io  # noqa: F401  (registers the 'cextxyz' format)
import extxyz

from bench_read import make_xyz   # reuse the synthetic-frame generator


def _best(fn, repeats):
    best = float('inf')
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=Path('benchmarks/cleri_results.csv'))
    ap.add_argument('--total', type=int, default=1_000_000,
                    help='approx total atoms per file (held ~constant)')
    ap.add_argument('--repeats', type=int, default=3)
    args = ap.parse_args()

    per_frame = [5, 10, 20, 50, 100, 500, 2000]

    hdr = (f'{"atoms/frame":>11}  {"frames":>7}  {"MB":>6}  '
           f'{"cleri":>9}  {"dispatch":>9}  {"speedup":>8}  {"full rd speedup":>15}')
    print(hdr); print('-' * len(hdr))

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for nat in per_frame:
            nframes = max(1, args.total // nat)
            path = Path(tmp) / f'f_{nat}.xyz'
            mb = make_xyz(path, nat, nframes) / 1e6
            sp = str(path)

            # parser only (read_dicts), per-atom tokenizer in both; comment parser differs
            t_cleri = _best(lambda: extxyz.read_dicts(sp, use_cleri=True), args.repeats)
            t_disp = _best(lambda: extxyz.read_dicts(sp, use_cleri=False), args.repeats)
            # full ASE plugin read, both ways
            t_cleri_full = _best(lambda: ase.io.read(sp, format='cextxyz', index=':',
                                                     use_cleri=True), args.repeats)
            t_disp_full = _best(lambda: ase.io.read(sp, format='cextxyz', index=':',
                                                    use_cleri=False), args.repeats)

            speedup = t_cleri / t_disp if t_disp else float('nan')
            full_speedup = t_cleri_full / t_disp_full if t_disp_full else float('nan')
            rows.append(dict(atoms_per_frame=nat, frames=nframes, file_mb=mb,
                             read_dicts_cleri_s=t_cleri, read_dicts_dispatch_s=t_disp,
                             dispatch_speedup=speedup,
                             full_read_cleri_s=t_cleri_full,
                             full_read_dispatch_s=t_disp_full,
                             full_read_speedup=full_speedup))
            print(f'{nat:>11}  {nframes:>7}  {mb:>6.1f}  '
                  f'{t_cleri:>8.3f}s  {t_disp:>8.3f}s  {speedup:>7.2f}x  '
                  f'{full_speedup:>14.2f}x')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f'Wrote {args.out}')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
