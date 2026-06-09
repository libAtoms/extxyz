"""The C writer must honor a custom float format (issue #22).

ASE's default 8-decimal output truncates positions, which breaks hash-equality
of Atoms before/after a write. The pure-Python writer already accepts a
``format_dict``; the C writer used to reject it. These tests check that the C
writer now applies a per-type ``format_dict`` (keyed R/I/S/L) to the per-atom
columns, so a higher-precision format round-trips, while the default output is
unchanged.
"""
import numpy as np
import pytest

from extxyz import Frame, read_dicts, write_dicts


def _frame():
    # positions with more than 8 significant decimals
    pos = np.array([[1.123456789012345, 2.0, 3.0],
                    [4.0, 5.987654321098765, 6.0]])
    return Frame(natoms=2,
                 cell=np.eye(3) * 20.0,
                 pbc=np.array([True, True, True]),
                 info={},
                 arrays={'species': np.array(['H', 'O']), 'pos': pos})


def _max_roundtrip_error(tmp_path, fmt):
    f = _frame()
    out = tmp_path / 'd.xyz'
    kw = {} if fmt is None else {'format_dict': {'R': fmt}}
    write_dicts(out, [f], use_cextxyz=True, **kw)
    back = read_dicts(out, use_cextxyz=True)
    return np.max(np.abs(back.arrays['pos'] - f.arrays['pos']))


def test_default_precision_truncates(tmp_path):
    """Sanity: the default %.8f format loses the high-precision digits (the
    bug behind issue #22). rtol=0 so the tiny absolute error is actually seen."""
    err = _max_roundtrip_error(tmp_path, None)
    assert err > 1e-11  # ~1e-9 truncation


def test_custom_precision_roundtrips(tmp_path):
    """A high-precision format_dict preserves the positions on the C path,
    and is strictly better than the default."""
    custom = _max_roundtrip_error(tmp_path, '%.16g')
    default = _max_roundtrip_error(tmp_path, None)
    assert custom < 1e-12
    assert custom < default


def test_custom_precision_no_valueerror(tmp_path):
    """The C writer no longer raises on format_dict (it used to)."""
    f = _frame()
    out = tmp_path / 'n.xyz'
    write_dicts(out, [f], use_cextxyz=True, format_dict={'R': '%.10f'})
    assert out.exists()


def test_default_output_unchanged(tmp_path):
    """No format_dict -> identical bytes to before (uses extxyz_write_ll)."""
    f = _frame()
    a = tmp_path / 'a.xyz'
    write_dicts(a, [f], use_cextxyz=True)
    # passing the C default format explicitly should match the default path
    b = tmp_path / 'b.xyz'
    write_dicts(b, [f], use_cextxyz=True,
                format_dict={'R': '%16.8f', 'I': '%8d', 'S': '%s', 'L': '%.1s'})
    assert a.read_text() == b.read_text()
