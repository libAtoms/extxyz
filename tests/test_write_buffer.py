"""The buffered C writer must produce byte-identical output and round-trip.

The per-atom write loop builds lines in a memory buffer and `fwrite`s them in
blocks instead of one `fprintf` per value. That's purely an I/O change, so the
bytes must be exactly what the per-cell `fprintf` writer produced — this golden
locks the format, and the round-trip checks values survive a write→read.
"""
import numpy as np

from extxyz import Frame, read_dicts, write_dicts


def _frame():
    return Frame(
        natoms=2, cell=np.diag([10.0, 11.0, 12.0]),
        pbc=np.array([True, False, True]),
        info={"energy": -1.5},
        arrays={"species": np.array(["H", "Cu"]),
                "pos": np.array([[1.123456789, -0.00623274, 0.0],
                                 [-20.0, 3.5, 12.03120730]]),
                "z": np.array([1, 29], dtype=np.int32)})


GOLDEN = (
    '2\n'
    'energy=-1.50000000 '
    'Lattice="10.00000000 0.00000000 0.00000000 0.00000000 11.00000000 '
    '0.00000000 0.00000000 0.00000000 12.00000000" pbc=[T, F, T] '
    'Properties=species:S:1:pos:R:3:z:I:1\n'
    'H         1.12345679      -0.00623274       0.00000000          1\n'
    'Cu       -20.00000000       3.50000000      12.03120730         29\n'
)


def test_write_bytes_are_golden(tmp_path):
    p = tmp_path / "g.xyz"
    write_dicts(p, [_frame()], use_cextxyz=True)
    assert p.read_text() == GOLDEN


def test_write_roundtrips(tmp_path):
    f = _frame()
    p = tmp_path / "rt.xyz"
    write_dicts(p, [f], use_cextxyz=True)
    back = read_dicts(p, use_cextxyz=True)
    assert list(back.arrays["species"]) == ["H", "Cu"]
    assert list(back.arrays["z"]) == [1, 29]
    # pos round-trips to the written 8-decimal precision
    np.testing.assert_allclose(back.arrays["pos"], f.arrays["pos"], atol=1e-8)
    assert (back.pbc == [True, False, True]).all()


def test_write_block_boundary(tmp_path):
    """A frame large enough to cross the internal flush threshold many times
    still round-trips exactly (exercises the buffer grow/flush path)."""
    n = 20000
    rng = np.random.default_rng(0)
    f = Frame(natoms=n, cell=np.eye(3) * 50, pbc=np.array([True] * 3), info={},
              arrays={"species": rng.choice(["H", "C", "N", "O"], size=n),
                      "pos": rng.random((n, 3)) * 40 - 20})
    p = tmp_path / "big.xyz"
    write_dicts(p, [f], use_cextxyz=True)
    back = read_dicts(p, use_cextxyz=True)
    assert list(back.arrays["species"]) == list(f.arrays["species"])
    np.testing.assert_allclose(back.arrays["pos"], f.arrays["pos"], atol=1e-8)
