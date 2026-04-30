"""Plot the read-time benchmark from ``bench_read.py``.

Usage::

    python benchmarks/plot_bench.py [--in benchmarks/results.csv]
                                    [--out benchmarks/read_speedup.png]
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--in', dest='inp', type=Path,
                        default=Path('benchmarks/results.csv'))
    parser.add_argument('--out', dest='outp', type=Path,
                        default=Path('benchmarks/read_speedup.png'))
    args = parser.parse_args()

    with args.inp.open() as f:
        rows = list(csv.DictReader(f))

    natoms = [int(r['natoms']) for r in rows]
    builtin = [float(r['builtin_s']) for r in rows]
    cext = [float(r['cextxyz_s']) for r in rows]
    dicts = [float(r['read_dicts_s']) for r in rows]
    speedup = [float(r['speedup']) for r in rows]
    parse_speedup = [float(r['parse_speedup']) for r in rows]

    fig, (ax_t, ax_s) = plt.subplots(1, 2, figsize=(11, 4.2))

    ax_t.loglog(natoms, builtin, 'o-', label="ASE built-in 'extxyz' (regex)",
                color='tab:red')
    ax_t.loglog(natoms, cext, 's-', label="ase-extxyz 'cextxyz' (full plugin)",
                color='tab:blue')
    ax_t.loglog(natoms, dicts, '^--',
                label="extxyz.read_dicts (parser only, no Atoms)",
                color='tab:green')
    ax_t.set_xlabel('atoms per frame')
    ax_t.set_ylabel('read time (s)')
    ax_t.set_title('Read time vs system size')
    ax_t.grid(True, which='both', alpha=0.3)
    ax_t.legend(loc='upper left', fontsize=9)

    ax_s.semilogx(natoms, speedup, 'o-',
                  label="full plugin / built-in", color='tab:blue')
    ax_s.semilogx(natoms, parse_speedup, '^--',
                  label="parser only / built-in", color='tab:green')
    ax_s.axhline(1, color='gray', linewidth=0.8, linestyle='--')
    ax_s.set_xlabel('atoms per frame')
    ax_s.set_ylabel('speedup (built-in / candidate)')
    ax_s.set_title('Speedup vs ASE built-in')
    ax_s.grid(True, which='both', alpha=0.3)
    ax_s.legend(loc='best', fontsize=9)

    fig.tight_layout()
    args.outp.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.outp, dpi=150)
    print(f'Wrote {args.outp}')


if __name__ == '__main__':
    main()
