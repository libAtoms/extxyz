"""Tests that exercise the ase.io plugin path end-to-end."""
import ase.io
import numpy as np
import pytest
from ase.build import bulk
from ase.io.formats import ioformats


def test_plugin_registered():
    """The cextxyz format must be discoverable via ase.io.formats.ioformats."""
    assert 'cextxyz' in ioformats, sorted(ioformats)


def test_read_via_ase_io(tmp_path):
    """ase.io.read(format='cextxyz') yields the right Atoms."""
    src = tmp_path / 'sample.xyz'
    src.write_text("""\
2
Lattice="2.0 0.0 0.0  0.0 2.0 0.0  0.0 0.0 2.0" Properties=species:S:1:pos:R:3 pbc=[T, T, T]
H 0.0 0.0 0.0
H 1.0 0.0 0.0
""")
    atoms = ase.io.read(str(src), format='cextxyz')
    assert len(atoms) == 2
    assert (atoms.numbers == [1, 1]).all()
    np.testing.assert_allclose(atoms.positions[1], [1.0, 0.0, 0.0])
    assert (atoms.pbc == [True, True, True]).all()
    np.testing.assert_allclose(np.diag(atoms.cell.array), [2.0, 2.0, 2.0])


def test_write_then_read_via_ase_io(tmp_path):
    out = tmp_path / 'out.xyz'
    atoms = bulk('Cu') * 2
    ase.io.write(str(out), atoms, format='cextxyz')
    back = ase.io.read(str(out), format='cextxyz')
    assert (back.numbers == atoms.numbers).all()
    np.testing.assert_allclose(back.positions, atoms.positions, atol=1e-7)
    np.testing.assert_allclose(back.cell.array, atoms.cell.array, atol=1e-7)


def test_multiple_frames_via_ase_io(tmp_path):
    out = tmp_path / 'multi.xyz'
    frames = [bulk('Cu'), bulk('Cu') * 2, bulk('Cu') * (1, 1, 2)]
    ase.io.write(str(out), frames, format='cextxyz')
    back = ase.io.read(str(out), format='cextxyz', index=':')
    assert isinstance(back, list)
    assert len(back) == len(frames)
    for orig, got in zip(frames, back):
        assert (orig.numbers == got.numbers).all()
        np.testing.assert_allclose(orig.positions, got.positions, atol=1e-7)


def test_index_argument(tmp_path):
    out = tmp_path / 'multi.xyz'
    frames = [bulk('Cu'), bulk('Cu') * 2, bulk('Cu') * (1, 1, 2)]
    ase.io.write(str(out), frames, format='cextxyz')
    only = ase.io.read(str(out), format='cextxyz', index=1)
    assert len(only) == len(frames[1])
    np.testing.assert_allclose(only.positions, frames[1].positions, atol=1e-7)


def test_trajectory_writer_streaming(tmp_path):
    """ExtXYZTrajectoryWriter keeps one FILE* open across writes — useful
    for attaching to long-running ASE optimizers/dynamics."""
    from ase_extxyz.io import ExtXYZTrajectoryWriter

    out = tmp_path / 'stream.xyz'
    frames = [bulk('Cu'), bulk('Cu') * 2, bulk('Cu') * (1, 1, 2)]
    with ExtXYZTrajectoryWriter(str(out)) as traj:
        for atoms in frames:
            traj.write(atoms)
    back = ase.io.read(str(out), format='cextxyz', index=':')
    assert len(back) == len(frames)
    for orig, got in zip(frames, back):
        assert (orig.numbers == got.numbers).all()
        np.testing.assert_allclose(orig.positions, got.positions, atol=1e-7)


def test_trajectory_writer_callable_for_optimizers(tmp_path):
    """Optimizer.attach calls the trajectory directly; __call__ delegates to write()."""
    from ase_extxyz.io import ExtXYZTrajectoryWriter

    out = tmp_path / 'opt.xyz'
    atoms = bulk('Cu') * 2
    with ExtXYZTrajectoryWriter(str(out), atoms=atoms) as traj:
        # opt.attach(traj) calls traj() per step; uses the captured atoms
        traj()
        atoms.positions += 0.01
        traj()
    back = ase.io.read(str(out), format='cextxyz', index=':')
    assert len(back) == 2
