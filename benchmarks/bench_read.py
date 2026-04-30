"""Benchmark: cextxyz plugin vs ASE built-in extxyz reader.

Generates synthetic extxyz files of varying atom counts and times reading
each one with both ``format='extxyz'`` (ASE built-in, regex-based) and
``format='cextxyz'`` (this repo's C parser via the ase-extxyz plugin).

Run::

    python benchmarks/bench_read.py [--out benchmarks/results.csv]
                                    [--max-atoms 100000]
                                    [--repeats 3]

Output:
- CSV table at the chosen path with columns:
    natoms, frames, file_mb, builtin_s, cextxyz_s, speedup
- Stdout: pretty table for the README.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import ase.io
from ase.build import bulk

import extxyz
# Make sure the cextxyz plugin is registered (comes from ase-extxyz).
import ase_extxyz.io  # noqa: F401


def make_xyz(path: Path, natoms: int, n_frames: int = 1) -> int:
    """Write a synthetic extxyz file with `natoms` atoms per frame, repeated
    `n_frames` times. Returns the file size in bytes.
    """
    base = bulk('Cu')
    n_repeat = max(1, int(round((natoms / len(base)) ** (1 / 3))))
    atoms = base * (n_repeat, n_repeat, n_repeat)
    # Trim to exact target if the cube root rounded too high.
    if len(atoms) > natoms:
        atoms = atoms[:natoms]
    # If it rounded too low, pad by tiling along x.
    while len(atoms) < natoms:
        atoms = atoms * (2, 1, 1)
    atoms = atoms[:natoms]

    # Add a few realistic info/array entries so the parser has work to do.
    # Avoid 'stress' / 'virial' — ASE's built-in extxyz parser is picky about
    # its 3x3 matrix encoding and our cextxyz writer's JSON-style encoding
    # doesn't match its expectations. The benchmark is about parser speed,
    # not encoding compatibility.
    atoms.info['energy'] = -1.234
    atoms.info['step'] = 42
    atoms.set_array('forces', np.random.normal(0, 0.05, (natoms, 3)))

    # Write through the cextxyz plugin (fast) so file generation isn't a bottleneck.
    ase.io.write(str(path), [atoms] * n_frames, format='cextxyz')
    return path.stat().st_size


def _best_of(fn, repeats: int) -> float:
    best = float('inf')
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - t0
        # touch the data to defeat any lazy decoding
        if isinstance(result, list):
            _ = result[-1]
        if elapsed < best:
            best = elapsed
    return best


def time_read_ase(path: Path, fmt: str, repeats: int) -> float:
    return _best_of(lambda: ase.io.read(str(path), format=fmt, index=':'), repeats)


def time_read_dicts(path: Path, repeats: int) -> float:
    """Time the ASE-free dict-based reader — what extxyz.read_dicts costs."""
    return _best_of(lambda: extxyz.read_dicts(str(path)), repeats)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path,
                        default=Path('benchmarks/results.csv'))
    parser.add_argument('--max-atoms', type=int, default=100_000)
    parser.add_argument('--frames', type=int, default=1,
                        help='frames per file (default 1)')
    parser.add_argument('--repeats', type=int, default=3,
                        help='best-of-N timings (default 3)')
    args = parser.parse_args()

    # Geometric sweep of system sizes.
    sizes = []
    n = 10
    while n <= args.max_atoms:
        sizes.append(n)
        n *= 10 if n < 1000 else 4 if n < args.max_atoms / 4 else args.max_atoms
        if n > args.max_atoms:
            break
    if sizes[-1] != args.max_atoms:
        sizes.append(args.max_atoms)

    rows = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    header = (f'{"N atoms":>10}  {"frames":>6}  {"file MB":>8}  '
              f'{"builtin":>10}  {"cextxyz":>10}  {"read_dicts":>11}  '
              f'{"speedup":>8}  {"parse_speedup":>14}')
    print(header)
    print('-' * len(header))

    with tempfile.TemporaryDirectory() as tmpdir:
        for n in sizes:
            path = Path(tmpdir) / f'bench_{n}.xyz'
            size_bytes = make_xyz(path, n, args.frames)
            t_builtin = time_read_ase(path, 'extxyz', args.repeats)
            t_cext = time_read_ase(path, 'cextxyz', args.repeats)
            t_dicts = time_read_dicts(path, args.repeats)
            speedup = t_builtin / t_cext if t_cext > 0 else float('nan')
            parse_speedup = t_builtin / t_dicts if t_dicts > 0 else float('nan')
            row = dict(natoms=n, frames=args.frames,
                       file_mb=size_bytes / 1e6,
                       builtin_s=t_builtin, cextxyz_s=t_cext,
                       read_dicts_s=t_dicts,
                       speedup=speedup,
                       parse_speedup=parse_speedup)
            rows.append(row)
            print(f'{n:>10}  {args.frames:>6}  {row["file_mb"]:>8.2f}  '
                  f'{t_builtin:>10.4f}  {t_cext:>10.4f}  {t_dicts:>11.4f}  '
                  f'{speedup:>7.2f}x  {parse_speedup:>13.2f}x')

    with args.out.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f'\nWrote {args.out}')


if __name__ == '__main__':
    main()
