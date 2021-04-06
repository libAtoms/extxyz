from pathlib import Path
import numpy as np


def test_one_elem_scalar(tmp_path, helpers):
    helpers.do_test_kv_pair(tmp_path, 'i', 1, 'i="1"')
    helpers.do_test_kv_pair(tmp_path, 'i', 1, 'i={1}')


def test_new_non_symm_3_by_3(tmp_path, helpers):
    helpers.do_test_kv_pair(tmp_path, 'lat', [[1,2,3],[4,5,6],[7,8,9]], 'lat=[[1, 2, 3], [4, 5, 6], [7, 8, 9]]')


def test_old_nine_elem_non_symm_3_by_3(tmp_path, helpers):
    helpers.do_test_kv_pair(tmp_path, 'lat', [[1,4,7],[2,5,8],[3,6,9]], 'lat="1 2 3  4 5 6  7 8 9"')
    helpers.do_test_kv_pair(tmp_path, 'lat', [[1,4,7],[2,5,8],[3,6,9]], 'lat={1 2 3  4 5 6  7 8 9}')


def test_new_non_symm_Lattice(tmp_path, helpers):
    with open(tmp_path / Path('test_file.extxyz'), 'w') as fout:
        fout.write(f'1\nProperties=species:S:1:pos:R:3 Lattice=[[1, 2, 3], [4, 5, 6], [7, 8, 9]]\nSi 0.0 0.0 0.0\n')

    for at in helpers.read_all_variants(tmp_path / Path('test_file.extxyz')):
        # print("new format got cell", at.cell)
        assert np.all(at.cell == [[1,2,3], [4,5,6], [7,8,9]])


def test_old_nine_elem_non_symm_Lattice(tmp_path, helpers):
    with open(tmp_path / Path('test_file.extxyz'), 'w') as fout:
        fout.write(f'1\nProperties=species:S:1:pos:R:3 Lattice="1 2 3  4 5 6   7 8 9"\nSi 0.0 0.0 0.0\n')

    for at in helpers.read_all_variants(tmp_path / Path('test_file.extxyz')):
        # print("old format got cell", at.cell)
        assert np.all(at.cell == [[1,2,3], [4,5,6], [7,8,9]])

    with open(tmp_path / Path('test_file.extxyz'), 'w') as fout:
        fout.write('1\nProperties=species:S:1:pos:R:3 Lattice={1 2 3  4 5 6  7 8 9}\nSi 0.0 0.0 0.0\n')

    for at in helpers.read_all_variants(tmp_path / Path('test_file.extxyz')):
        # print("old format got cell", at.cell)
        assert np.all(at.cell == [[1,2,3], [4,5,6], [7,8,9]])
