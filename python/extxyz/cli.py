"""Standalone command-line driver for the extxyz parser.

Parses one or more frames from an extxyz file and dumps them as JSON
(via :class:`extxyz.grammar.ExtXYZEncoder`). Optionally round-trips through
the writer to verify ``read → write → read`` is idempotent.

This entry point intentionally has no ASE dependency so it works from a
plain ``pip install extxyz``.
"""
import argparse
import cProfile
import json
import os
import time

from .core import Frame, read_dicts, write_dicts
from .grammar import ExtXYZEncoder


def _frame_to_jsonable(frame: Frame) -> dict:
    return {
        'natoms': frame.natoms,
        'cell': frame.cell,
        'pbc': frame.pbc,
        'info': frame.info,
        'arrays': {k: v for k, v in frame.arrays.items()},
    }


def main():
    parser = argparse.ArgumentParser(description='extxyz parser CLI (no ASE).')
    parser.add_argument('file')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    parser.add_argument('-r', '--regex', action='store_true',
                        help='use the regex-based pure-Python parser')
    parser.add_argument('-w', '--write', action='store_true',
                        help='round-trip-write to <file>.out.xyz')
    parser.add_argument('-R', '--round-trip', action='store_true',
                        help='also re-read the written file and compare')
    parser.add_argument('-P', '--profile', action='store_true')
    parser.add_argument('-C', '--cextxyz', action='store_true',
                        help='use the C parser (default: pure-Python)')
    parser.add_argument('--comment', action='store', default=None)
    args = parser.parse_args()
    if args.round_trip:
        args.write = True

    read_kwargs = dict(verbose=args.verbose,
                       use_regex=args.regex,
                       use_cextxyz=args.cextxyz,
                       comment=args.comment)

    print(f'Reading from {args.file}')
    if args.profile:
        cProfile.run('frames = read_dicts(args.file, **read_kwargs)', 'readstats')
    t0 = time.time()
    frames = read_dicts(args.file, **read_kwargs)
    tr = time.time() - t0
    if isinstance(frames, Frame):
        frames = [frames]
    print(f'TIMER read {tr:.4f}s ({len(frames)} frame(s))')
    if args.verbose:
        print(json.dumps([_frame_to_jsonable(f) for f in frames],
                         cls=ExtXYZEncoder, indent=2))

    if args.write:
        out_file = os.path.splitext(args.file)[0] + '.out.xyz'
        write_kwargs = dict(verbose=args.verbose, use_cextxyz=args.cextxyz)
        t0 = time.time()
        if args.profile:
            cProfile.run('write_dicts(out_file, frames, **write_kwargs)', 'writestats')
        else:
            write_dicts(out_file, frames, **write_kwargs)
        tw = time.time() - t0
        print(f'TIMER write {tw:.4f}s')

        if args.round_trip:
            print(f'Re-reading from {out_file}')
            new_frames = read_dicts(out_file, **read_kwargs)
            if isinstance(new_frames, Frame):
                new_frames = [new_frames]
            assert len(frames) == len(new_frames), \
                f'frame count mismatch: {len(frames)} vs {len(new_frames)}'
            print('Frames round-tripped (count matches; deep compare not implemented).')
