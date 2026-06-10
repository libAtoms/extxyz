"""Plot the read- or write-time benchmark.

Auto-detects which it is from the CSV columns: ``read_dicts_s`` (from
``bench_read.py``) or ``write_dicts_s`` (from ``bench_write.py``).

Usage::

    python benchmarks/plot_bench.py                                  # read_speedup.png
    python benchmarks/plot_bench.py --in benchmarks/write_results.csv \
                                    --out benchmarks/write_speedup.png
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

    writing = 'write_dicts_s' in rows[0]
    verb = 'write' if writing else 'read'
    ours_col = 'write_dicts_s' if writing else 'read_dicts_s'
    ours_speedup_col = 'write_speedup' if writing else 'parse_speedup'
    ours_label = ("extxyz.write_dicts (C writer, no Atoms)" if writing
                  else "extxyz.read_dicts (parser only, no Atoms)")
    ours_sp_label = ("C writer / built-in" if writing else "parser only / built-in")

    natoms = [int(r['natoms']) for r in rows]
    builtin = [float(r['builtin_s']) for r in rows]
    cext = [float(r['cextxyz_s']) for r in rows]
    ours = [float(r[ours_col]) for r in rows]
    speedup = [float(r['speedup']) for r in rows]
    ours_speedup = [float(r[ours_speedup_col]) for r in rows]
    # optional opt-in tokenizer columns (read CSV, added later)
    has_fast = 'read_dicts_fast_s' in rows[0]
    if has_fast:
        dicts_fast = [float(r['read_dicts_fast_s']) for r in rows]
        fast_speedup = [float(r['fast_speedup']) for r in rows]

    fig, (ax_t, ax_s) = plt.subplots(1, 2, figsize=(11, 4.2))

    builtin_label = ("ASE built-in 'extxyz'" if writing
                     else "ASE built-in 'extxyz' (regex)")
    ax_t.loglog(natoms, builtin, 'o-', label=builtin_label, color='tab:red')
    ax_t.loglog(natoms, cext, 's-', label="ase-extxyz 'cextxyz' (full plugin)",
                color='tab:blue')
    ax_t.loglog(natoms, ours, '^--', label=ours_label, color='tab:green')
    if has_fast:
        ax_t.loglog(natoms, dicts_fast, 'v:',
                    label="read_dicts, tokenizer (use_regex=False)",
                    color='tab:purple')
    ax_t.set_xlabel('atoms per frame')
    ax_t.set_ylabel(f'{verb} time (s)')
    ax_t.set_title(f'{verb.capitalize()} time vs system size')
    ax_t.grid(True, which='both', alpha=0.3)
    ax_t.legend(loc='upper left', fontsize=9)

    ax_s.semilogx(natoms, speedup, 'o-',
                  label="full plugin / built-in", color='tab:blue')
    ax_s.semilogx(natoms, ours_speedup, '^--',
                  label=ours_sp_label, color='tab:green')
    if has_fast:
        ax_s.semilogx(natoms, fast_speedup, 'v:',
                      label="parser, tokenizer / built-in", color='tab:purple')
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
