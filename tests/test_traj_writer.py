"""Tests for ExtXYZTrajectoryWriter — the convenience wrapper that's
exported in extxyz.__all__ and shown in the README's usage example.
"""
import numpy as np
from ase.atoms import Atoms
from ase.build import bulk

from extxyz import ExtXYZTrajectoryWriter, read


def _make_frames(n=3):
    a = bulk('Cu') * 2
    frames = []
    for i in range(n):
        f = a.copy()
        f.positions += 0.001 * (i + 1)
        frames.append(f)
    return frames


def _assert_frames_equal(got, original, atol=1e-7):
    assert (got.numbers == original.numbers).all()
    assert np.allclose(got.cell.array, original.cell.array, atol=atol)
    assert (got.pbc == original.pbc).all()
    assert np.allclose(got.positions, original.positions, atol=atol)


def test_write_then_read(tmp_path):
    out = tmp_path / 'traj.xyz'
    frames = _make_frames(3)

    writer = ExtXYZTrajectoryWriter(out)
    for f in frames:
        writer.write(f)
    writer.close()

    read_back = read(out)
    assert isinstance(read_back, list)
    assert len(read_back) == 3
    for original, got in zip(frames, read_back):
        _assert_frames_equal(got, original)


def test_context_manager_closes_file(tmp_path):
    out = tmp_path / 'traj_ctx.xyz'
    frames = _make_frames(2)

    with ExtXYZTrajectoryWriter(out) as writer:
        for f in frames:
            writer.write(f)
        # while still open, file handle should be live
        assert not writer.file.closed
    # __exit__ should have closed it
    assert writer.file.closed

    read_back = read(out)
    if isinstance(read_back, Atoms):
        read_back = [read_back]
    assert len(read_back) == len(frames)


def test_default_atoms_argument(tmp_path):
    """Writer can be constructed with a fixed atoms; subsequent .write()
    with no arg should use that one (the ASE-optimizer attachment style)."""
    out = tmp_path / 'traj_default.xyz'
    a = bulk('Si')

    with ExtXYZTrajectoryWriter(out, atoms=a) as writer:
        writer.write()
        a.positions += 0.01
        writer.write()

    read_back = read(out)
    assert isinstance(read_back, list)
    assert len(read_back) == 2


def test_append_mode(tmp_path):
    out = tmp_path / 'traj_app.xyz'
    a = bulk('Cu')

    with ExtXYZTrajectoryWriter(out, mode='w') as w:
        w.write(a)
    with ExtXYZTrajectoryWriter(out, mode='a') as w:
        w.write(a)
        w.write(a)

    read_back = read(out)
    assert isinstance(read_back, list)
    assert len(read_back) == 3
