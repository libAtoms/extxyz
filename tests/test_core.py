"""ASE-free smoke tests for the dict/array core API."""
import io

import numpy as np
import pytest

import extxyz
from extxyz import Frame, iread_dicts, read_dicts, write_dicts


SAMPLE = """\
2
Lattice="2.0 0.0 0.0  0.0 2.0 0.0  0.0 0.0 2.0" Properties=species:S:1:pos:R:3 pbc=[T, T, T] energy=-1.5
H 0.0 0.0 0.0
H 1.0 0.0 0.0
3
Lattice="3.0 0.0 0.0  0.0 3.0 0.0  0.0 0.0 3.0" Properties=species:S:1:pos:R:3 pbc=[T, T, T] step=42
O 0.0 0.0 0.0
H 0.96 0.0 0.0
H -0.24 0.93 0.0
"""


@pytest.fixture
def sample_path(tmp_path):
    p = tmp_path / 'sample.xyz'
    p.write_text(SAMPLE)
    return p


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_iread_yields_frames(sample_path, use_cextxyz):
    frames = list(iread_dicts(sample_path, use_cextxyz=use_cextxyz))
    assert len(frames) == 2
    f0, f1 = frames
    assert isinstance(f0, Frame)
    assert f0.natoms == 2
    assert f1.natoms == 3
    assert f0.info['energy'] == pytest.approx(-1.5)
    assert f1.info['step'] == 42
    assert (f0.pbc == [True, True, True]).all()
    assert f0.cell.shape == (3, 3)
    assert (f0.cell == np.diag([2.0, 2.0, 2.0])).all()
    assert 'pos' in f0.arrays and 'species' in f0.arrays
    assert f1.arrays['pos'].shape == (3, 3)


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_read_returns_list_when_multiple(sample_path, use_cextxyz):
    out = read_dicts(sample_path, use_cextxyz=use_cextxyz)
    assert isinstance(out, list)
    assert len(out) == 2


def test_read_returns_single_when_one_frame(tmp_path):
    p = tmp_path / 'one.xyz'
    p.write_text(SAMPLE.split('\n3\n')[0] + '\n')
    out = read_dicts(p, use_cextxyz=False)
    assert isinstance(out, Frame)


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_round_trip(sample_path, tmp_path, use_cextxyz):
    frames = list(iread_dicts(sample_path, use_cextxyz=use_cextxyz))
    out = tmp_path / 'roundtrip.xyz'
    write_dicts(out, frames, use_cextxyz=use_cextxyz)
    re_read = list(iread_dicts(out, use_cextxyz=use_cextxyz))
    assert len(re_read) == len(frames)
    for orig, got in zip(frames, re_read):
        assert orig.natoms == got.natoms
        np.testing.assert_allclose(orig.cell, got.cell, atol=1e-7)
        assert (orig.pbc == got.pbc).all()
        np.testing.assert_allclose(orig.arrays['pos'], got.arrays['pos'], atol=1e-7)


def test_index_argument(sample_path):
    """Single-int index returns just that frame; slice returns a slice."""
    f = list(iread_dicts(sample_path, index=1, use_cextxyz=False))
    assert len(f) == 1
    assert f[0].natoms == 3

    f = list(iread_dicts(sample_path, index=slice(0, 1), use_cextxyz=False))
    assert len(f) == 1
    assert f[0].natoms == 2


def test_no_ase_dependency():
    """Importing extxyz in a fresh subprocess must not pull in any ase.* module.

    Run as a subprocess so other tests (or ase-extxyz, when both are
    installed in the same venv) don't pollute sys.modules.
    """
    import subprocess
    import sys
    code = (
        "import sys\n"
        "import extxyz\n"
        "leaked = sorted(m for m in sys.modules if m == 'ase' or m.startswith('ase.'))\n"
        "assert not leaked, f'ase leaked: {leaked}'\n"
    )
    subprocess.run([sys.executable, '-c', code], check=True)


def test_legacy_names_raise_helpful_importerror():
    """The pre-0.3 top-level names should raise ImportError pointing at ase-extxyz."""
    from extxyz.extxyz import read, write, iread, ExtXYZTrajectoryWriter

    for fn in (read, write, iread):
        with pytest.raises(ImportError, match=r'ase-extxyz'):
            fn('whatever')

    with pytest.raises(ImportError, match=r'ase-extxyz'):
        ExtXYZTrajectoryWriter('out.xyz')
