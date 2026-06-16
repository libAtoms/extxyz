"""Parity tests: the C-API marshalling (_extxyz.read_frame, libextxyz/pyext.c)
must produce output byte-for-byte identical to the legacy ctypes marshalling
(cextxyz.c_to_py_dict). Both go through cextxyz.read_frame_dicts; the dispatcher
honours cextxyz._USE_LEGACY_MARSHAL per call, so we read each file both ways.
"""
import numpy as np
import pytest

import extxyz
from extxyz import cextxyz

pytestmark = pytest.mark.skipif(
    not cextxyz._HAVE_C_READ,
    reason="C-API fast read path not built (numpy-less build)")


# A comment line exercising every info type: str/bool/int/float scalars,
# 1D int/float/bool arrays, a 2D int array (virial) and the 3x3 Lattice.
COMPLEX_COMMENT = (
    'str=astring quot="quoted value" false_value=F integer=22 floating=1.1 '
    'int_array="1 2 3" float_array="3.3 4.4" '
    'virial="[[1, 2, 3], [4, 5, 6], [7, 8, 9]]" '
    'Lattice="4.3 0 0 0 3.3 0 0 0 7.0" '
    'scientific_float=1.2e7 sci_array="1.2 2200 40 0.33 0.02" '
    'bool_array="T F T F" energy="-79.178441" pbc="T T F" '
    'Properties=species:S:1:pos:R:3'
)

# A frame with rich per-atom columns: string (species), float matrix (pos,
# force), int vector (tag), bool vector (flag).
RICH_PERATOM = (
    '3\n'
    'Lattice="10 0 0 0 10 0 0 0 10" '
    'Properties=species:S:1:pos:R:3:tag:I:1:flag:L:1:force:R:3\n'
    'C 0.1 0.2 0.3 5 T 1.5 -2.5 3.5\n'
    'Hh 1.1 -1.2 1.3 -7 F 0.0 0.0 -0.0\n'
    'O 2.25 2.5 -2.75 0 T 9.0 8.0 7.0\n'
)

FRAMES = {
    'complex_info': '1\n{}\nH 1.0 1.0 1.0\n'.format(COMPLEX_COMMENT),
    'rich_peratom': RICH_PERATOM,
    'multi_frame': RICH_PERATOM + '1\n{}\nH 1.0 1.0 1.0\n'.format(COMPLEX_COMMENT),
}


@pytest.fixture(autouse=True)
def _restore_marshal_flag():
    saved = cextxyz._USE_LEGACY_MARSHAL
    yield
    cextxyz._USE_LEGACY_MARSHAL = saved


def _read(path, legacy, use_regex):
    cextxyz._USE_LEGACY_MARSHAL = legacy
    out = extxyz.read_dicts(str(path), use_regex=use_regex)
    return out if isinstance(out, list) else [out]


def _assert_value_equal(label, a, b):
    a_arr, b_arr = isinstance(a, np.ndarray), isinstance(b, np.ndarray)
    assert a_arr == b_arr, f"{label}: array-ness {a_arr} != {b_arr}"
    if a_arr:
        assert a.dtype == b.dtype, f"{label}: dtype {a.dtype} != {b.dtype}"
        assert a.shape == b.shape, f"{label}: shape {a.shape} != {b.shape}"
        if a.dtype.kind == 'f':
            # bit-identical, not merely close
            assert np.array_equal(a.view('u8'), b.view('u8')), f"{label}: float bits differ"
        else:
            assert np.array_equal(a, b), f"{label}: values differ"
    else:
        assert type(a) is type(b), f"{label}: type {type(a)} != {type(b)}"
        assert a == b, f"{label}: {a!r} != {b!r}"


@pytest.mark.parametrize('use_regex', [False, True])
@pytest.mark.parametrize('name', list(FRAMES))
def test_c_marshalling_matches_legacy(tmp_path, name, use_regex):
    path = tmp_path / f'{name}.xyz'
    path.write_text(FRAMES[name])

    new = _read(path, legacy=False, use_regex=use_regex)
    old = _read(path, legacy=True, use_regex=use_regex)

    assert len(new) == len(old)
    for i, (a, b) in enumerate(zip(new, old)):
        assert a.natoms == b.natoms, f"frame {i}: natoms"
        _assert_value_equal(f"frame {i}.cell", a.cell, b.cell)
        assert (a.pbc == b.pbc).all(), f"frame {i}: pbc"
        assert set(a.info) == set(b.info), f"frame {i}: info keys"
        for k in a.info:
            _assert_value_equal(f"frame {i}.info[{k!r}]", a.info[k], b.info[k])
        assert set(a.arrays) == set(b.arrays), f"frame {i}: arrays keys"
        for k in a.arrays:
            _assert_value_equal(f"frame {i}.arrays[{k!r}]", a.arrays[k], b.arrays[k])


def test_c_path_raises_eof_at_end():
    """read_frame raises EOFError past the last frame, just like the ctypes path
    (this is what lets iread_dicts terminate)."""
    import tempfile, os
    fd, name = tempfile.mkstemp(suffix='.xyz')
    os.write(fd, b'1\nProperties=species:S:1:pos:R:3\nH 0 0 0\n')
    os.close(fd)
    try:
        fp = cextxyz.cfopen(name, 'r')
        try:
            cextxyz._ext_mod.read_frame(cextxyz._kv_grammar.value, fp.value, 1, None)
            with pytest.raises(EOFError):
                cextxyz._ext_mod.read_frame(cextxyz._kv_grammar.value, fp.value, 1, None)
        finally:
            cextxyz.cfclose(fp)
    finally:
        os.unlink(name)


@pytest.mark.parametrize('legacy', [False, True])
def test_malformed_raises_extxyz_error(tmp_path, legacy):
    """Both backends reject a malformed per-atom line with ExtXYZError."""
    path = tmp_path / 'bad.xyz'
    path.write_text('1\nProperties=species:S:1:pos:R:3\nH NOTANUM 0 0\n')
    with pytest.raises(cextxyz.ExtXYZError):
        _read(path, legacy=legacy, use_regex=False)
