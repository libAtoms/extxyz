"""The tokenizer read mode (use_regex=False on the C backend, the default).

It must (a) produce bit-identical results to the strict regex parser for valid
files, and (b) reject malformed per-atom fields with a clear error instead of
silently mis-parsing (which atoi/atof would do).
"""
import os
import tempfile

import numpy as np
import pytest

from extxyz import read_dicts, cextxyz


VALID_BODIES = [
    # species + pos, typical
    '2\nLattice="3 0 0 0 3 0 0 0 3" Properties=species:S:1:pos:R:3 energy=-1.5\n'
    'H 0.0 1.0 2.0\nO 3.0 4.0 5.0\n',
    # scientific, Fortran d, signed, leading-dot floats, tabs as separators
    '2\nProperties=species:S:1:pos:R:3\nH\t1.0e1\t-.5\t3.0d0\nO  -2.5  .25  +0.0\n',
    # every column type, multi-column string, bool variants
    '3\nLattice="5 0 0 0 5 0 0 0 5" Properties=tag:S:2:pos:R:3:z:I:1:ok:L:1 step=7\n'
    'a bb 0 1 2 7 T\nccc d 3 4 5 -2 false\ne ffff 6 7 8 0 True\n',
    # high-precision floats (fallback path) + leading whitespace on rows
    '1\nProperties=species:S:1:pos:R:3\n   Ne 1.123456789012345 1.2345678901234567 9.876543e-5\n',
]


def _read_both(body):
    with tempfile.NamedTemporaryFile("w", suffix=".xyz", delete=False) as f:
        f.write(body)
        p = f.name
    try:
        regex = read_dicts(p, use_cextxyz=True, use_regex=True)
        fast = read_dicts(p, use_cextxyz=True, use_regex=False)
    finally:
        os.unlink(p)
    return regex, fast


@pytest.mark.parametrize("body", VALID_BODIES)
def test_tokenizer_matches_regex(body):
    regex, fast = _read_both(body)
    rframes = regex if isinstance(regex, list) else [regex]
    fframes = fast if isinstance(fast, list) else [fast]
    assert len(rframes) == len(fframes)
    for r, f in zip(rframes, fframes):
        assert r.arrays.keys() == f.arrays.keys()
        for k in r.arrays:
            a, b = r.arrays[k], f.arrays[k]
            if a.dtype.kind == "f":
                # bit-identical floats, not just close
                assert np.array_equal(a.view("u8"), b.view("u8")), k
            else:
                assert np.array_equal(a, b), k
        np.testing.assert_array_equal(r.cell, f.cell)
        assert (r.pbc == f.pbc).all()


@pytest.mark.parametrize("body", [
    "1\nProperties=species:S:1:pos:R:3\nH NOTANUM 0 0\n",      # bad float
    "1\nProperties=species:S:1:pos:R:3\nH 1.2.3 0 0\n",        # bad float
    "1\nProperties=species:S:1:pos:R:3\nH inf 0 0\n",          # inf rejected
    "1\nProperties=z:I:1:pos:R:3\n12x 0 0 0\n",                # bad int
    "1\nProperties=b:L:1:pos:R:3\nmaybe 0 0 0\n",              # bad bool
    "1\nProperties=species:S:1:pos:R:3\nH 0 0\n",              # too few fields
    "1\nProperties=species:S:1:pos:R:3\nH 0 0 0 EXTRA\n",      # too many fields
])
def test_tokenizer_rejects_malformed(tmp_path, body):
    p = tmp_path / "bad.xyz"
    p.write_text(body)
    with pytest.raises(cextxyz.ExtXYZError):
        read_dicts(p, use_cextxyz=True, use_regex=False)


def test_tokenizer_is_default(tmp_path):
    """use_regex defaults to False (tokenizer) since v0.4.2: a default read
    matches an explicit use_regex=False read, and malformed numerics are
    still rejected."""
    good = tmp_path / "good.xyz"
    good.write_text('1\nLattice="3 0 0 0 3 0 0 0 3" Properties=species:S:1:pos:R:3\n'
                    'H 0.1 0.2 0.3\n')
    default = read_dicts(good, use_cextxyz=True)
    fast = read_dicts(good, use_cextxyz=True, use_regex=False)
    assert default.arrays.keys() == fast.arrays.keys()
    assert np.array_equal(default.arrays['pos'], fast.arrays['pos'])

    bad = tmp_path / "bad.xyz"
    bad.write_text("1\nProperties=species:S:1:pos:R:3\nH NOTANUM 0 0\n")
    with pytest.raises(cextxyz.ExtXYZError):
        read_dicts(bad, use_cextxyz=True)   # default tokenizer
