"""The fast per-atom float parser must be bit-exact with the strtod path.

`atof_eEdD` has a fast path for plain decimals with <= 15 significant digits
(where `mant / 10**frac` is a single correctly-rounded division) and falls back
to strtod for exponents, 16+ digits, or anything else. Either way the parsed
double must be bit-identical to what strtod/Python's float() produces, so write
precision (issue #22) and round-tripping are unaffected.
"""
import os
import tempfile

import numpy as np
import pytest

from extxyz import cextxyz


# strings spanning: typical %.8f, >15 sig digits (fallback), scientific
# (fallback), Fortran d/D exponent (fallback), signs, zeros, leading dot.
FLOAT_STRINGS = [
    "0.0", "-0.0", "1.0", "-1.0", "19.00927393", "-0.00623274",
    "1.123456789012345",      # 16 chars, 16 sig -> fallback
    "1.2345678901234567",     # 17 sig -> fallback
    "123456789012345.6",      # 16 sig -> fallback
    "0.000000001", ".5", "-.25", "+3.5", "42",
    "9.876543210987653e-05",  # scientific -> fallback
    "1.5e3", "-2.25E-2",      # scientific -> fallback
    "1.5d3", "2.0D-1",        # Fortran d/D exponent -> fallback
]


def _read_floats(strings):
    body = f"{len(strings)}\nProperties=x:R:1\n" + "".join(s + "\n" for s in strings)
    with tempfile.NamedTemporaryFile("w", suffix=".xyz", delete=False) as f:
        f.write(body)
        path = f.name
    fp = cextxyz.cfopen(path, "r")
    try:
        _, _, arrays = cextxyz.read_frame_dicts(fp)
    finally:
        cextxyz.cfclose(fp)
        os.unlink(path)
    return arrays["x"]


def test_fast_float_is_bit_exact():
    got = _read_floats(FLOAT_STRINGS)
    # reference: Python float() == strtod; d/D -> e for the Fortran forms
    ref = np.array([float(s.replace("d", "e").replace("D", "E"))
                    for s in FLOAT_STRINGS])
    # compare the raw bits, not approximately
    assert np.array_equal(got.view("u8"), ref.view("u8")), \
        list(zip(FLOAT_STRINGS, got, ref))


@pytest.mark.parametrize("s,expected", [
    ("19.00927393", 19.00927393),
    ("1.2345678901234567", 1.2345678901234567),   # fallback path
    ("1.5e3", 1500.0),                              # scientific fallback
    ("1.5d3", 1500.0),                              # Fortran d exponent fallback
    ("-0.0", -0.0),
])
def test_fast_float_values(s, expected):
    got = _read_floats([s])[0]
    assert got == expected and np.signbit(got) == np.signbit(expected)
