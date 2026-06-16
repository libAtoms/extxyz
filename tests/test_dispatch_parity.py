"""Differential conformance: the first-char dispatch comment-line parser
(use_cleri=False) must accept the same language and produce byte-identical
results to the libcleri grammar (use_cleri=True). This test IS the provability
mechanism — cleri stays the canonical grammar/oracle.
"""
import random

import numpy as np
import pytest

import extxyz
from extxyz import cextxyz

pytestmark = pytest.mark.skipif(
    not cextxyz._HAVE_C_READ,
    reason="C read path not built")

# Comment-line bodies (appended after the mandatory Properties=...) covering
# every value shape: scalars, 1D/2D bracket arrays, old "..."/{...} containers,
# the string-fallback backtracks, scientific floats, quoted/escaped keys.
BODIES = [
    'energy=-1.5 step=42 ok=T name=astring',
    'q="quoted value" e="esc\\"aped"',
    'iarr="1 2 3" farr="3.3 4.4" barr="T F T"',
    'v=[1, 2, 3] f=[1.5, 2.5] b=[T, F]',
    'm=[[1, 2, 3], [4, 5, 6], [7, 8, 9]]',
    'lat="1 2 3  4 5 6  7 8 9"',
    'cb={1 2 3} cbs={a b c}',
    'sci=1.2e7 sci2=5e-6 sciarr="1.2 2200 0.33"',
    'notnum="1.0 2.0 3.0 7.0 8.09.0"',          # -> string (backtrack)
    'notbool="T F S" single="1" mixed="1 2 x"',  # -> string / scalar
    'bob#joe=2 "with space"=3 "sp\\"q"=4',
    'pbc="T T F" subset="MC2D"',
    'twostr=[["a", "b"], ["c", "d"]]',
]

PROPS = "Properties=species:S:1:pos:R:3"
ATOM = "Si 0.0 0.0 0.0"


def _frame(body):
    return f"1\n{PROPS} {body}\n{ATOM}\n"


def _read(path, use_cleri):
    out = extxyz.read_dicts(str(path), use_cextxyz=True, use_cleri=use_cleri)
    return out if isinstance(out, list) else [out]


def _assert_equal(label, a, b):
    aa, ba = isinstance(a, np.ndarray), isinstance(b, np.ndarray)
    assert aa == ba, f"{label}: array-ness {aa} != {ba} ({a!r} vs {b!r})"
    if aa:
        assert a.dtype == b.dtype, f"{label}: dtype {a.dtype} != {b.dtype}"
        assert a.shape == b.shape, f"{label}: shape {a.shape} != {b.shape}"
        if a.dtype.kind == 'f':
            assert np.array_equal(a.view('u8'), b.view('u8')), f"{label}: float bits"
        else:
            assert np.array_equal(a, b), f"{label}: values {a!r} != {b!r}"
    else:
        assert type(a) is type(b), f"{label}: type {type(a)} != {type(b)}"
        assert a == b, f"{label}: {a!r} != {b!r}"


def _compare(path):
    cl = _read(path, use_cleri=True)
    ds = _read(path, use_cleri=False)
    assert len(cl) == len(ds)
    for i, (a, b) in enumerate(zip(cl, ds)):
        assert a.natoms == b.natoms, f"frame {i} natoms"
        _assert_equal(f"frame{i}.cell", a.cell, b.cell)
        assert (a.pbc == b.pbc).all(), f"frame {i} pbc"
        assert set(a.info) == set(b.info), f"frame {i} info keys {set(a.info) ^ set(b.info)}"
        for k in a.info:
            _assert_equal(f"frame{i}.info[{k!r}]", a.info[k], b.info[k])
        assert set(a.arrays) == set(b.arrays), f"frame {i} arrays keys"
        for k in a.arrays:
            _assert_equal(f"frame{i}.arrays[{k!r}]", a.arrays[k], b.arrays[k])


@pytest.mark.parametrize("body", BODIES)
def test_dispatch_matches_cleri(tmp_path, body):
    path = tmp_path / "f.xyz"
    path.write_text(_frame(body))
    _compare(path)


def test_dispatch_matches_cleri_multiframe(tmp_path):
    path = tmp_path / "multi.xyz"
    path.write_text("".join(_frame(b) for b in BODIES))
    _compare(path)


# --- randomized differential fuzz over grammar-valid kv lines ---

def _rand_value(rng):
    kind = rng.choice(["int", "float", "bool", "bare", "qstr",
                       "iarr", "farr", "barr", "old", "m2d"])
    if kind == "int":
        return str(rng.randint(-9999, 9999))
    if kind == "float":
        return rng.choice([f"{rng.uniform(-1e3, 1e3):.6g}",
                           f"{rng.uniform(-1, 1):.3e}", f"{rng.randint(0,99)}."])
    if kind == "bool":
        return rng.choice(["T", "F", "true", "false", "TRUE", "FALSE"])
    if kind == "bare":
        return "".join(rng.choice("abcXYZ_0123") for _ in range(rng.randint(1, 6))) or "x"
    if kind == "qstr":
        return '"' + rng.choice(["a b", "hello world", "x_1 y_2"]) + '"'
    if kind == "iarr":
        return "[" + ", ".join(str(rng.randint(-50, 50)) for _ in range(rng.randint(1, 4))) + "]"
    if kind == "farr":
        return "[" + ", ".join(f"{rng.uniform(-9, 9):.4g}" for _ in range(rng.randint(1, 4))) + "]"
    if kind == "barr":
        return "[" + ", ".join(rng.choice(["T", "F"]) for _ in range(rng.randint(1, 4))) + "]"
    if kind == "old":
        return '"' + " ".join(str(rng.randint(-9, 9)) for _ in range(rng.randint(2, 5))) + '"'
    # m2d
    nc = rng.randint(1, 3)
    nr = rng.randint(2, 3)
    rows = ["[" + ", ".join(str(rng.randint(-9, 9)) for _ in range(nc)) + "]" for _ in range(nr)]
    return "[" + ", ".join(rows) + "]"


def test_dispatch_matches_cleri_fuzz(tmp_path):
    rng = random.Random(20260616)
    path = tmp_path / "fuzz.xyz"
    frames = []
    for _ in range(300):
        nkv = rng.randint(1, 6)
        keys = [f"k{j}{rng.randint(0,99)}" for j in range(nkv)]
        body = " ".join(f"{k}={_rand_value(rng)}" for k in keys)
        frames.append(_frame(body))
    path.write_text("".join(frames))
    _compare(path)


# --- reject parity (at the read_frame_dicts level, bypassing core.py's
#     plain-xyz retry fallback) ---

MALFORMED = [
    "Properties=species:S:1:pos:R:3 bad",          # bare key, no '='
    "Properties=species:S:1:pos:R:3 k=1.2.3.4",    # invalid value -> reject? compare
    "Properties=pos:R:3:species",                   # malformed Properties
    "Properties=species:S:1:pos:R:3 k=[1, 2",      # unterminated array
    "Properties=species:S:1:pos:R:3 'sq'=1",       # single-quoted key not in grammar
]


@pytest.mark.parametrize("line", MALFORMED)
def test_dispatch_reject_matches_cleri(tmp_path, line):
    """Both backends must agree on accept/reject for the raw comment line."""
    def parse(use_cleri):
        p = tmp_path / "m.xyz"
        p.write_text(f"1\n{line}\nSi 0 0 0\n")
        fp = cextxyz.cfopen(str(p), "r")
        try:
            cextxyz.read_frame_dicts(fp, use_cleri=use_cleri)
            return True   # accepted
        except cextxyz.ExtXYZError:
            return False  # rejected
        finally:
            cextxyz.cfclose(fp)

    assert parse(True) == parse(False), f"accept/reject disagree on {line!r}"
