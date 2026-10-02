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


def _triclinic():
    from ase import Atoms
    cell = [[4.0, 0.0, 0.0], [1.0, 3.0, 0.0], [0.5, 0.7, 2.0]]     # rows a1, a2, a3: not symmetric
    return Atoms('Si2', scaled_positions=[[0, 0, 0], [0.3, 0.4, 0.5]], cell=cell, pbc=True)


@pytest.mark.parametrize('read_c', [True, False])
@pytest.mark.parametrize('write_c', [True, False])
def test_triclinic_cell_round_trips(tmp_path, write_c, read_c):
    """Every cell in the other round-trip tests is symmetric, where a transpose of the
    lattice is invisible; a triclinic cell must survive both writers and both readers,
    and ASE's own extxyz reader (an independent parser) must read the same cell."""
    from ase_extxyz.io import read_cextxyz, write_cextxyz
    atoms = _triclinic()
    out = tmp_path / 'tri.xyz'
    write_cextxyz(str(out), atoms, use_cextxyz=write_c)
    (back,) = read_cextxyz(str(out), index=0, use_cextxyz=read_c)     # a generator of Atoms
    np.testing.assert_allclose(back.cell.array, atoms.cell.array, atol=1e-7)
    np.testing.assert_allclose(back.positions, atoms.positions, atol=1e-7)
    np.testing.assert_allclose(ase.io.read(str(out), format='extxyz').cell.array, atoms.cell.array, atol=1e-7)


def test_trajectory_writer_keeps_a_triclinic_cell(tmp_path):
    from ase_extxyz.io import ExtXYZTrajectoryWriter, read_cextxyz
    atoms = _triclinic()
    out = tmp_path / 'traj.xyz'
    w = ExtXYZTrajectoryWriter(str(out))
    w.write(atoms)
    w.close()
    (back,) = read_cextxyz(str(out), index=0)
    np.testing.assert_allclose(back.cell.array, atoms.cell.array, atol=1e-7)
    np.testing.assert_allclose(ase.io.read(str(out), format='extxyz').cell.array, atoms.cell.array, atol=1e-7)
