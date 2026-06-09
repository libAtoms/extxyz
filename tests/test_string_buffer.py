"""Per-atom string columns read correctly regardless of internal storage.

These guard the contiguous fixed-width-buffer representation of string columns
(a perf change to the read path): behaviour must be identical to the old
per-pointer storage, including multi-column string properties and strings longer
than the initial cell width (which force the buffer to grow). The files are
written as text so the tests exercise only the read path.
"""
import numpy as np
import pytest

from extxyz import Frame, read_dicts, write_dicts


def _read_text(tmp_path, body, use_cextxyz):
    p = tmp_path / 'sb.xyz'
    p.write_text(body)
    return read_dicts(p, use_cextxyz=use_cextxyz)


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_species_read(tmp_path, use_cextxyz):
    body = ("4\n"
            'Lattice="10 0 0 0 10 0 0 0 10" Properties=species:S:1:pos:R:3\n'
            "H 0 0 0\nC 1 1 1\nN 2 2 2\nO 3 3 3\n")
    f = _read_text(tmp_path, body, use_cextxyz)
    assert list(f.arrays['species']) == ['H', 'C', 'N', 'O']
    np.testing.assert_allclose(f.arrays['pos'][3], [3, 3, 3])


def test_long_string_read_forces_width_growth(tmp_path):
    """A per-atom string far longer than any small initial cell width must be
    preserved in full by the C parser (exercises the buffer-grow path). Tested
    at the low level to bypass the structured-array dtype width cap in the
    high-level read path on master."""
    from extxyz import cextxyz
    longlabel = "verylongatomlabel_0123456789ABCDEF"
    p = tmp_path / 'long.xyz'
    p.write_text("3\nProperties=label:S:1:pos:R:3\n"
                 f"H 0 0 0\n{longlabel} 1 1 1\nO 2 2 2\n")
    fp = cextxyz.cfopen(str(p), 'r')
    try:
        nat, info, arrays = cextxyz.read_frame_dicts(fp)
    finally:
        cextxyz.cfclose(fp)
    assert list(arrays['label']) == ['H', longlabel, 'O']


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_multicolumn_string_read(tmp_path, use_cextxyz):
    """A 2-column string property exercises the matrix (nrows>0) string path."""
    body = ("3\n"
            "Properties=tag:S:2:pos:R:3\n"
            "a bb 0 0 0\nccc d 1 1 1\ne ffff 2 2 2\n")
    f = _read_text(tmp_path, body, use_cextxyz)
    assert f.arrays['tag'].shape == (3, 2)
    assert [list(r) for r in f.arrays['tag']] == [['a', 'bb'], ['ccc', 'd'], ['e', 'ffff']]


def test_species_roundtrip_short(tmp_path):
    """Write+read round-trip for the common short-1D-string case (C backend)."""
    f = Frame(natoms=4, cell=np.eye(3) * 10, pbc=np.array([True] * 3), info={},
              arrays={'species': np.array(['H', 'C', 'N', 'O']),
                      'pos': np.arange(12, dtype=float).reshape(4, 3)})
    p = tmp_path / 'rt.xyz'
    write_dicts(p, [f], use_cextxyz=True)
    back = read_dicts(p, use_cextxyz=True)
    assert list(back.arrays['species']) == ['H', 'C', 'N', 'O']
    np.testing.assert_allclose(back.arrays['pos'], f.arrays['pos'])
