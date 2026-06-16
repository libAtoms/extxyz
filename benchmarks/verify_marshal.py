"""Assert the C-API marshalling (_extxyz.read_frame) is byte-identical to the
legacy ctypes marshalling (c_to_py_dict), frame by frame.

Flips cextxyz._USE_LEGACY_MARSHAL in-process (the dispatcher reads it per call).
"""
import sys
import numpy as np
import extxyz
from extxyz import cextxyz

path = sys.argv[1] if len(sys.argv) > 1 else "mad-train.xyz"

assert cextxyz._HAVE_C_READ, "C read path not built — rebuild with numpy"


def read_all(legacy):
    cextxyz._USE_LEGACY_MARSHAL = legacy
    return extxyz.read_dicts(path)


new = read_all(False)
old = read_all(True)
cextxyz._USE_LEGACY_MARSHAL = False

assert len(new) == len(old), f"frame count {len(new)} != {len(old)}"
print(f"comparing {len(new)} frames ...")

bad = 0
for i, (a, b) in enumerate(zip(new, old)):
    def fail(msg):
        global bad
        bad += 1
        if bad <= 20:
            print(f"  frame {i}: {msg}")

    if a.natoms != b.natoms:
        fail(f"natoms {a.natoms} != {b.natoms}"); continue
    if not np.array_equal(a.cell.view('u8'), b.cell.view('u8')):
        fail("cell differs")
    if (a.pbc != b.pbc).any():
        fail("pbc differs")
    # info dict
    if set(a.info) != set(b.info):
        fail(f"info keys {set(a.info)} != {set(b.info)}"); continue
    for k in a.info:
        va, vb = a.info[k], b.info[k]
        if isinstance(va, np.ndarray) or isinstance(vb, np.ndarray):
            va, vb = np.asarray(va), np.asarray(vb)
            if va.shape != vb.shape or va.dtype != vb.dtype:
                fail(f"info[{k!r}] dtype/shape {va.dtype}{va.shape} != {vb.dtype}{vb.shape}")
            elif va.dtype.kind == 'f':
                if not np.array_equal(va.view('u8'), vb.view('u8')):
                    fail(f"info[{k!r}] float bits differ")
            elif not np.array_equal(va, vb):
                fail(f"info[{k!r}] differs")
        else:
            if type(va) is not type(vb) or va != vb:
                fail(f"info[{k!r}] {va!r} ({type(va).__name__}) != {vb!r} ({type(vb).__name__})")
    # arrays dict
    if set(a.arrays) != set(b.arrays):
        fail(f"arrays keys {set(a.arrays)} != {set(b.arrays)}"); continue
    for k in a.arrays:
        va, vb = a.arrays[k], b.arrays[k]
        if va.dtype != vb.dtype or va.shape != vb.shape:
            fail(f"arrays[{k!r}] dtype/shape {va.dtype}{va.shape} != {vb.dtype}{vb.shape}")
        elif va.dtype.kind == 'f':
            if not np.array_equal(va.view('u8'), vb.view('u8')):
                fail(f"arrays[{k!r}] float bits differ")
        elif not np.array_equal(va, vb):
            fail(f"arrays[{k!r}] differs")

print(f"DONE: {len(new)} frames, mismatches = {bad}")
sys.exit(1 if bad else 0)
