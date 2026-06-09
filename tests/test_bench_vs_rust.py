"""Head-to-head performance comparison: this C parser vs the Rust port.

The Rust port is published on PyPI as ``extxyz-ng`` but it *imports* as
``extxyz`` -- the same name as this project -- so the two cannot coexist in one
interpreter. This benchmark therefore runs the Rust port in a *separate*
Python interpreter (its own venv) via subprocess, and compares against our C
backend (cextxyz) run in this interpreter.

It is **skipped by default**. To run it, create a venv that has the Rust port
installed and point this test at its interpreter::

    python -m venv /tmp/ng && /tmp/ng/bin/pip install extxyz-ng
    EXTXYZ_NG_PYTHON=/tmp/ng/bin/python \\
        PYTHONPATH=python pytest tests/bench_vs_rust.py -s

The README's headline claim is ~4x faster / ~half the memory vs the *pre-JIT*
legacy C parser. This repo has since gained PCRE2 JIT + buffer aliasing, so the
point of this test is to measure the *current* gap and print it; the only hard
assertion is a loose sanity bound so the test never flakes on absolute numbers.
"""
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

NG_PYTHON = os.environ.get("EXTXYZ_NG_PYTHON")

pytestmark = pytest.mark.skipif(
    not NG_PYTHON,
    reason="set EXTXYZ_NG_PYTHON=<python in a venv with extxyz-ng installed> to run",
)


# ----------------------------------------------------------------------------
# Fixture generation
# ----------------------------------------------------------------------------
def _write_frame(fh, natoms, seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    pos = rng.random((natoms, 3)) * 20.0
    species = rng.choice(["H", "C", "N", "O"], size=natoms)
    fh.write(f"{natoms}\n")
    # NB: no `pbc=[T, T, T]` -- the Rust port (extxyz-ng 0.x) errors on bool
    # arrays, so we keep the info line to keys both parsers accept for fairness.
    fh.write('Lattice="20 0 0 0 20 0 0 0 20" '
             "Properties=species:S:1:pos:R:3 energy=-123.456\n")
    for s, (x, y, z) in zip(species, pos):
        fh.write(f"{s} {x:.8f} {y:.8f} {z:.8f}\n")


@pytest.fixture(scope="module")
def big_frame(tmp_path_factory):
    p = tmp_path_factory.mktemp("bench") / "big.xyz"
    with open(p, "w") as fh:
        _write_frame(fh, 20000, seed=1)
    return p


@pytest.fixture(scope="module")
def trajectory(tmp_path_factory):
    p = tmp_path_factory.mktemp("bench") / "traj.xyz"
    with open(p, "w") as fh:
        for i in range(200):
            _write_frame(fh, 500, seed=i)
    return p


# ----------------------------------------------------------------------------
# Timing helpers
# ----------------------------------------------------------------------------
def _time(fn, repeat=5):
    fn()  # warmup
    best = min(_one(fn) for _ in range(repeat))
    return best


def _one(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def _run_ng(path, multi, repeat=5):
    """Run the Rust port in its own interpreter.

    Returns ``(seconds, None)`` on success or ``(None, error_str)`` if the Rust
    port failed to parse the file (its multi-frame reader desyncs on realistic
    trajectories -- see test_bench_trajectory).
    """
    snippet = textwrap.dedent(
        f"""
        import time
        import extxyz
        path = {str(path)!r}
        multi = {bool(multi)}
        def run():
            if multi:
                n = 0
                for _ in extxyz.read_frames_from_file(path):
                    n += 1
                return n
            else:
                extxyz.read_frame_from_file(path)
        run()  # warmup
        best = None
        for _ in range({repeat}):
            t0 = time.perf_counter()
            run()
            dt = time.perf_counter() - t0
            best = dt if best is None else min(best, dt)
        print(best)
        """
    )
    # Strip PYTHONPATH so the Rust-port venv imports its *own* `extxyz`, not
    # this project's source tree (both packages are named `extxyz`).
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    out = subprocess.run([NG_PYTHON, "-c", snippet], env=env,
                         capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        return None, out.stderr.strip().splitlines()[-1] if out.stderr else "unknown error"
    return float(out.stdout.strip().splitlines()[-1]), None


# ----------------------------------------------------------------------------
# Benchmarks
# ----------------------------------------------------------------------------
def test_bench_single_large_frame(big_frame):
    from extxyz import read_dicts
    ours = _time(lambda: read_dicts(big_frame, use_cextxyz=True))
    theirs, err = _run_ng(big_frame, multi=False)
    _report("single 20k-atom frame", ours, theirs, err, big_frame)
    # loose sanity bound: ours must at least complete and be in the same ballpark
    assert ours < 10.0
    assert theirs is not None, f"extxyz-ng failed to read a single frame: {err}"


def test_bench_trajectory(trajectory):
    """Trajectory read. NOTE: extxyz-ng's multi-frame reader desyncs after a
    few non-trivial frames, so it typically *fails* here -- which is itself the
    headline result. We report that and still measure our own throughput."""
    from extxyz import read_dicts
    ours = _time(lambda: read_dicts(trajectory, use_cextxyz=True))
    theirs, err = _run_ng(trajectory, multi=True)
    _report("200x500-atom trajectory", ours, theirs, err, trajectory)
    assert ours < 30.0
    # Don't fail the suite on extxyz-ng's bug; the _report line documents it.


def _report(label, ours, theirs, err, path):
    mb = Path(path).stat().st_size / 1e6
    print(f"\n[bench] {label}  ({mb:.2f} MB)")
    print(f"  ours (cextxyz, JIT): {ours*1e3:8.2f} ms")
    if theirs is None:
        print(f"  extxyz-ng (Rust):    FAILED to read ({err})")
        return
    print(f"  extxyz-ng (Rust):    {theirs*1e3:8.2f} ms")
    faster = "ours" if ours < theirs else "extxyz-ng"
    print(f"  -> {faster} faster by {max(ours, theirs)/min(ours, theirs):.2f}x")
