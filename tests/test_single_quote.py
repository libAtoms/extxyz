"""Single-quoted values must parse as a backward-compatible container,
equivalent to double quotes (issue #5, parser-only part).

The old Fortran/C reader treated ``'``, ``"`` and ``{}`` equivalently. The new
implementation had dropped ``'`` support, so real-world files using e.g.
``pbc='F F F'`` failed (the pure-Python backend raised; the C backend silently
fell back to defaults). This restores ``'`` as a quote container equivalent to
``"`` (ints/floats/bools, not strings — the string-only-container proposal is
deferred). ``'hello'`` therefore stays a bare string.
"""
import tempfile
import os

import numpy as np
import pytest

from extxyz import read_dicts


def _info(line, use_cextxyz, tmp_path):
    p = tmp_path / "sq.xyz"
    p.write_text(f"1\nProperties=species:S:1:pos:R:3 {line}\nH 0 0 0\n")
    return read_dicts(p, use_cextxyz=use_cextxyz)


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_single_quote_bool_array_pbc(tmp_path, use_cextxyz):
    """The real-world case from issue #8: pbc='F F F'."""
    frame = _info("pbc='F F F'", use_cextxyz, tmp_path)
    assert (frame.pbc == [False, False, False]).all()


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_single_quote_int_array(tmp_path, use_cextxyz):
    frame = _info("k='1 2 3'", use_cextxyz, tmp_path)
    assert np.array_equal(frame.info["k"], [1, 2, 3])


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_single_quote_scalar(tmp_path, use_cextxyz):
    """A single-element backward-compat array is a scalar (like \"3\")."""
    frame = _info("k='3'", use_cextxyz, tmp_path)
    assert frame.info["k"] == 3


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_single_quote_equivalent_to_double(tmp_path, use_cextxyz):
    sq = _info("k='1 2 3'", use_cextxyz, tmp_path)
    dq = _info('k="1 2 3"', use_cextxyz, tmp_path)
    assert np.array_equal(sq.info["k"], dq.info["k"])


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_quoted_word_stays_barestring(tmp_path, use_cextxyz):
    """'hello' is not numeric/bool, so it remains a bare string (quotes kept)."""
    frame = _info("k='hello'", use_cextxyz, tmp_path)
    assert frame.info["k"] == "'hello'"
