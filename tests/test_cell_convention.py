"""Frame.cell holds the lattice vectors as COLUMNS (cell[:, i] = a_i). The readers
follow that for both Lattice syntaxes: the old 9-number form lists a1, a2, a3 in turn,
and the nested 3x3 form is the matrix as written, vectors as its columns (as
tests/.../test_new_non_symm_Lattice pins). Both writers applied an extra transpose,
so every non-symmetric cell came back transposed from a read/write round trip; every
other test used a diagonal cell, where a transpose is invisible."""
import numpy as np
import pytest

import extxyz
from extxyz import Frame

A = np.array([[4.0, 0.0, 0.0], [1.0, 3.0, 0.0], [0.5, 0.7, 2.0]])     # rows: a1, a2, a3 (triclinic)
NINE = 'Lattice="4 0 0 1 3 0 0.5 0.7 2"'
NESTED_COLS = 'Lattice=[[4, 1, 0.5], [0, 3, 0.7], [0, 0, 2]]'     # the cell matrix: columns a1, a2, a3
BOTH = [True, False]


def _file(tmp_path, lattice):
    p = tmp_path / "f.xyz"
    p.write_text(f'2\n{lattice} Properties=species:S:1:pos:R:3 pbc="T T T"\nSi 0 0 0\nSi 1 1 1\n')
    return p


def _frame():
    return Frame(natoms=2, cell=A.T.copy(), pbc=np.array([True] * 3), info={},
                 arrays={"species": np.array(["Si", "Si"]), "pos": np.array([[0.0, 0, 0], [1, 1, 1]])})


READERS = [dict(use_cextxyz=True), dict(use_cextxyz=True, use_cleri=False), dict(use_cextxyz=False)]
READER_IDS = ["c-cleri", "c-dispatch", "python"]


@pytest.mark.parametrize("reader", READERS, ids=READER_IDS)
@pytest.mark.parametrize("lattice", [NINE, NESTED_COLS], ids=["nine", "nested"])
def test_read_gives_vectors_as_columns(tmp_path, lattice, reader):
    f = next(extxyz.iread_dicts(str(_file(tmp_path, lattice)), **reader))
    np.testing.assert_array_equal(f.cell, A.T)


@pytest.mark.parametrize("use_c", BOTH)
def test_write_emits_the_vectors_in_order(tmp_path, use_c):
    p = tmp_path / "w.xyz"
    extxyz.write_dicts(str(p), [_frame()], use_cextxyz=use_c)
    lat = p.read_text().splitlines()[1].split("Lattice=")[1]
    nested = lat.startswith("[")
    nums = [float(x) for x in lat.replace("[", " ").replace("]", " ").replace(",", " ")
            .replace('"', " ").split()[:9]]
    M = np.reshape(nums, (3, 3))
    assert not nested                                  # both writers emit the old-style 9-number form
    np.testing.assert_allclose(M, A)                   # a1, a2, a3 in turn


@pytest.mark.parametrize("reader", READERS, ids=READER_IDS)
@pytest.mark.parametrize("write_c", BOTH)
def test_round_trip_keeps_a_triclinic_cell(tmp_path, write_c, reader):
    src = next(extxyz.iread_dicts(str(_file(tmp_path, NINE))))
    p = tmp_path / "rt.xyz"
    extxyz.write_dicts(str(p), [src], use_cextxyz=write_c)
    back = next(extxyz.iread_dicts(str(p), **reader))
    np.testing.assert_allclose(back.cell, src.cell)
