
# additional tests of the extended XYZ file I/O
# (which is also included in oi.py test case)
# maintained by James Kermode <james.kermode@gmail.com>

from pathlib import Path
import numpy as np
import pytest

from extxyz.extxyz import read

 
from ase.io.extxyz import key_val_str_to_dict, key_val_dict_to_str

# import ase.io
# from ase.io import extxyz
# from ase.atoms import Atoms
from ase.build import bulk
# from ase.io.extxyz import escape
# from ase.calculators.calculator import compare_atoms
# from ase.calculators.emt import EMT
# from ase.constraints import FixAtoms, FixCartesian
# from ase.stress import full_3x3_to_voigt_6_stress
# from ase.build import molecule

# array data of shape (N, 1) squeezed down to shape (N, ) -- bug fixed
# in commit r4541


@pytest.fixture
def at():
    return bulk('Si')


@pytest.fixture
def images(at):
    images = [at, at * (2, 1, 1), at * (3, 1, 1)]
    images[1].set_pbc([True, True, False])
    images[2].set_pbc([True, False, False])
    return images

def write_ats(filename, ats, vec_cell=False):
    with open(filename, 'w') as fout:
        for at in ats:
            fout.write(f'{len(at)}\n')
            if not vec_cell:
                fout.write('Lattice="{} {} {}  {} {} {}  {} {} {}" Properties=species:S:1:pos:R:3 pbc=[{}, {}, {}]\n'.format(
                    *at.cell[0,:], *at.cell[1,:], *at.cell[2,:], *at.pbc))
            else:
                fout.write('\n')

            for s, p in zip(at.symbols, at.positions):
                fout.write('{}   {} {} {}\n'.format(s, *p))

            if vec_cell:
                if at.pbc[0]:
                    fout.write('VEC1 {} {} {}\n'.format(*at.cell[0,:]))
                if at.pbc[1]:
                    fout.write('VEC2 {} {} {}\n'.format(*at.cell[1,:]))
                if at.pbc[2]:
                    fout.write('VEC3 {} {} {}\n'.format(*at.cell[2,:]))

# write sequence of images with different numbers of atoms 
def test_sequence(tmp_path, images):
    write_ats(tmp_path / 'multi.xyz', images)

    read_images = read(str(tmp_path / 'multi.xyz'))
    assert read_images == images
 
### no support for vec_cell
##def test_vec_cell(at, images):
##    ase.io.write('multi.xyz', images, vec_cell=True)
##    cell = images[1].get_cell()
##    cell[-1] = [0.0, 0.0, 0.0]
##    images[1].set_cell(cell)
##    cell = images[2].get_cell()
##    cell[-1] = [0.0, 0.0, 0.0]
##    cell[-2] = [0.0, 0.0, 0.0]
##    images[2].set_cell(cell)
##    read_images = ase.io.read('multi.xyz', index=':')
##    assert read_images == images
##    # also test for vec_cell with whitespaces
##    Path('structure.xyz').write_text("""1
##    Coordinates
##    C         -7.28250        4.71303       -3.82016
##      VEC1 1.0 0.1 1.1
##    1
##
##    C         -7.28250        4.71303       -3.82016
##    VEC1 1.0 0.1 1.1
##    """)
##
##    a = ase.io.read('structure.xyz', index=0)
##    b = ase.io.read('structure.xyz', index=1)
##    assert a == b
##
##    # read xyz containing trailing blank line
##    # also test for upper case elements
##    Path('structure.xyz').write_text("""4
##    Coordinates
##    MG        -4.25650        3.79180       -2.54123
##    C         -1.15405        2.86652       -1.26699
##    C         -5.53758        3.70936        0.63504
##    C         -7.28250        4.71303       -3.82016
##
##    """)
##
##    a = ase.io.read('structure.xyz')
##    assert a[0].symbol == 'Mg'


# read xyz with / and @ signs in key value
def test_read_slash(tmp_path):
    (tmp_path / 'slash.xyz').write_text("""4
    key1=a key2=a/b key3=a@b key4="a@b"
    Mg        -4.25650        3.79180       -2.54123
    C         -1.15405        2.86652       -1.26699
    C         -5.53758        3.70936        0.63504
    C         -7.28250        4.71303       -3.82016
    """)

    with open(tmp_path / 'slash.xyz') as fin:
        print(''.join(fin.readlines()))

    a = read('slash.xyz')
    assert a.info['key1'] == r'a'
    assert a.info['key2'] == r'a/b'
    assert a.info['key3'] == r'a@b'
    assert a.info['key4'] == r'a@b'


# writing not supported
##def test_read_struct():
##    struct = Atoms(
##        'H4', pbc=[True, True, True],
##        cell=[[4.00759, 0.0, 0.0],
##              [-2.003795, 3.47067475, 0.0],
##              [3.06349683e-16, 5.30613216e-16, 5.00307]],
##        positions=[[-2.003795e-05, 2.31379473, 0.875437189],
##                   [2.00381504, 1.15688001, 4.12763281],
##                   [2.00381504, 1.15688001, 3.37697219],
##                   [-2.003795e-05, 2.31379473, 1.62609781]],
##    )
##    struct.info = {'dataset': 'deltatest', 'kpoints': np.array([28, 28, 20]),
##                   'identifier': 'deltatest_H_1.00',
##                   'unique_id': '4cf83e2f89c795fb7eaf9662e77542c1'}
##    ase.io.write('tmp.xyz', struct)


# Complex properties line. Keys and values that break with a regex parser.
# see https://gitlab.com/ase/ase/issues/53 for more info
def test_complex_key_val():
    complex_xyz_string = (
        ' '  # start with a separator
        'str=astring '
        'quot="quoted value" '
        'quote_special="a_to_Z_$%%^&*" '
        r'escaped_quote="esc\"aped" '
        #NB 'true_value ' bare key no longer valid
        'false_value = F '
        'integer=22 '
        'floating=1.1 '
        'int_array={1 2 3} '
        'float_array="3.3 4.4" '
        'virial="1 4 7 2 5 8 3 6 9" '  # special 3x3, fortran ordering
        'not_a_3x3_array="1 4 7 2 5 8 3 6 9" '  # should be left as a 9-vector
        'Lattice="  4.3  0.0 0.0 0.0  3.3 0.0 0.0 0.0  7.0 " '  # spaces in arr
        'scientific_float=1.2e7 '
        'scientific_float_2=5e-6 '
        'scientific_float_array="1.2 2.2e3 4e1 3.3e-1 2e-2" '
        'not_array="1.2 3.4 text" '
        'bool_array={T F T F} '
        'bool_array_2=" T, F, T " '  # leading spaces
        #NB 'not_bool_array=[T F S] ' bare string surrounded by [] no longer valid, maybe it should be
        # read and write
        # '\xfcnicode_key=val\xfce '  # fails on AppVeyor
        'unquoted_special_value=a_to_Z_$%%^&* '
        '2body=33.3 '
        #NB 'hyphen-ated ' bare key no longer valid, but trying hyphenated key with value
        'hyphen-ated=value '
        # parse only
        'many_other_quotes="4 8 12" '
        'comma_separated="7, 4, -1" '
        'bool_array_commas=[T, T, F, T] '
        'Properties=species:S:1:pos:R:3 '
        #NB 'multiple_separators       ' bare keyword no longer valid, try with a value
        'multiple_separators=val       '
        #NB 'double_equals=abc=xyz ' no longer allow bare = in value, must be quoted
        'double_equals="abc=xyz" '
        #NB 'trailing ' bare keyword no longer valid
        '"with space"="a value" '
        r'space\"="a value" '
        # tests of JSON functionality
        'f_str_looks_like_array="[[1, 2, 3], [4, 5, 6]]" '
        'f_float_array="_JSON [[1.5, 2, 3], [4, 5, 6]]" '
        'f_int_array="_JSON [[1, 2], [3, 4]]" '
        #NB 'f_bool_bare ' bare key no longer valid
        'f_bool_value=F '
        #NB 'f_dict={_JSON {"a" : 1}} ' no longer supporting quoting a string in {} instead of ""
    )

    expected_dict = {
        'str': 'astring',
        'quot': "quoted value",
        'quote_special': u"a_to_Z_$%%^&*",
        'escaped_quote': 'esc"aped',
        #NB 'true_value': True,
        'false_value': False,
        'integer': 22,
        'floating': 1.1,
        'int_array': np.array([1, 2, 3]),
        'float_array': np.array([3.3, 4.4]),
        'virial': np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
        'not_a_3x3_array': np.array([1, 4, 7, 2, 5, 8, 3, 6, 9]),
        'Lattice': np.array([[4.3, 0.0, 0.0],
                             [0.0, 3.3, 0.0],
                             [0.0, 0.0, 7.0]]),
        'scientific_float': 1.2e7,
        'scientific_float_2': 5e-6,
        'scientific_float_array': np.array([1.2, 2200, 40, 0.33, 0.02]),
        'not_array': "1.2 3.4 text",
        'bool_array': np.array([True, False, True, False]),
        'bool_array_2': np.array([True, False, True]),
        #NB 'not_bool_array': 'T F S',
        # '\xfcnicode_key': 'val\xfce',  # fails on AppVeyor
        'unquoted_special_value': 'a_to_Z_$%%^&*',
        '2body': 33.3,
        #NB 'hyphen-ated': True,
        'hyphen-ated': 'value',
        'many_other_quotes': np.array([4, 8, 12]),
        'comma_separated': np.array([7, 4, -1]),
        'bool_array_commas': np.array([True, True, False, True]),
        'Properties': 'species:S:1:pos:R:3',
        'multiple_separators': 'val',
        'double_equals': 'abc=xyz',
        #NB 'trailing': True,
        'with space': 'a value',
        'space"': 'a value',
        'f_str_looks_like_array': '[[1, 2, 3], [4, 5, 6]]',
        'f_float_array': np.array([[1.5, 2, 3], [4, 5, 6]]),
        'f_int_array': np.array([[1, 2], [3, 4]]),
        #NB 'f_bool_bare': True,
        'f_bool_value': False,
        #NB 'f_dict': {"a": 1} 
    }

    parsed_dict = key_val_str_to_dict(complex_xyz_string)
    np.testing.assert_equal(parsed_dict, expected_dict)

    key_val_str = key_val_dict_to_str(expected_dict)
    parsed_dict = key_val_str_to_dict(key_val_str)
    np.testing.assert_equal(parsed_dict, expected_dict)

    # Round trip through a file with complex line.
    # Create file with the complex line and re-read it afterwards.
    with open('complex.xyz', 'w', encoding='utf-8') as f_out:
        f_out.write('1\n{}\nH 1.0 1.0 1.0'.format(complex_xyz_string))
    complex_atoms = read('complex.xyz')

    # test all keys end up in info, as expected
    for key, value in expected_dict.items():
        if key in ['Properties', 'Lattice']:
            continue  # goes elsewhere
        else:
            np.testing.assert_equal(complex_atoms.info[key], value)


##def test_write_multiple(at, images):
##    # write multiple atoms objects to one xyz
##    for atoms in images:
##        atoms.write('append.xyz', append=True)
##        atoms.write('comp_append.xyz.gz', append=True)
##        atoms.write('not_append.xyz', append=False)
##    readFrames = ase.io.read('append.xyz', index=slice(0, None))
##    assert readFrames == images
##    readFrames = ase.io.read('comp_append.xyz.gz', index=slice(0, None))
##    assert readFrames == images
##    singleFrame = ase.io.read('not_append.xyz', index=slice(0, None))
##    assert singleFrame[-1] == images[-1]
##
##
### read xyz with blank comment line
##def test_blank_comment():
##    Path('blankcomment.xyz').write_text("""4
##
##    Mg        -4.25650        3.79180       -2.54123
##    C         -1.15405        2.86652       -1.26699
##    C         -5.53758        3.70936        0.63504
##    C         -7.28250        4.71303       -3.82016
##    """)
##
##    a = ase.io.read('blankcomment.xyz')
##    assert a.info == {}
##
##
##def test_escape():
##    assert escape('plain_string') == 'plain_string'
##    assert escape('string_containing_"') == r'"string_containing_\""'
##    assert escape('string with spaces') == '"string with spaces"'
##
##
##@pytest.mark.filterwarnings('ignore:write_xyz')
##def test_stress():
##    # build a water dimer, which has 6 atoms
##    water1 = molecule('H2O')
##    water2 = molecule('H2O')
##    water2.positions[:, 0] += 5.0
##    atoms = water1 + water2
##    atoms.cell = [10, 10, 10]
##    atoms.pbc = True
##
##    # array with clashing name
##    atoms.new_array('stress', np.arange(6, dtype=float))
##    atoms.calc = EMT()
##    a_stress = atoms.get_stress()
##    atoms.write('tmp.xyz')
##    b = ase.io.read('tmp.xyz')
##    assert abs(b.get_stress() - a_stress).max() < 1e-6
##    assert abs(b.arrays['stress'] - np.arange(6, dtype=float)).max() < 1e-6
##    b_stress = b.info['stress']
##    assert abs(full_3x3_to_voigt_6_stress(b_stress) - a_stress).max() < 1e-6
##
##
##def test_json_scalars():
##    a = bulk('Si')
##    a.info['val_1'] = 42.0
##    a.info['val_2'] = 42.0  # was np.float but that's the same.  Can remove
##    a.info['val_3'] = np.int64(42)
##    a.write('tmp.xyz')
##    with open('tmp.xyz', 'r') as fd:
##        comment_line = fd.readlines()[1]
##    assert "val_1=42.0" in comment_line and "val_2=42.0" in comment_line and "val_3=42" in comment_line
##    b = ase.io.read('tmp.xyz')
##    assert abs(b.info['val_1'] - 42.0) < 1e-6
##    assert abs(b.info['val_2'] - 42.0) < 1e-6
##    assert abs(b.info['val_3'] - 42) == 0
##
##
##@pytest.mark.parametrize('constraint', [FixAtoms(indices=(0, 2)),
##                                        FixCartesian(1, mask=(1, 0, 1)),
##                                        [FixCartesian(0), FixCartesian(2)]])
##def test_constraints(constraint):
##    atoms = molecule('H2O')
##    atoms.set_constraint(constraint)
##
##    columns = ['symbols', 'positions', 'move_mask']
##    ase.io.write('tmp.xyz', atoms, columns=columns)
##
##    atoms2 = ase.io.read('tmp.xyz')
##    assert not compare_atoms(atoms, atoms2)
##
##    constraint2 = atoms2.constraints
##    cls = type(constraint)
##    if cls == FixAtoms:
##        assert len(constraint2) == 1
##        assert isinstance(constraint2[0], cls)
##        assert np.all(constraint2[0].index == constraint.index)
##    elif cls == FixCartesian:
##        assert len(constraint2) == len(atoms)
##        assert isinstance(constraint2[0], cls)
##        assert np.all(constraint2[0].mask)
##        assert np.all(constraint2[1].mask == constraint.mask)
##        assert np.all(constraint2[2].mask)
##    elif cls == list:
##        assert len(constraint2) == len(atoms)
##        assert np.all(constraint2[0].mask == constraint[0].mask)
##        assert np.all(constraint2[1].mask)
##        assert np.all(constraint2[2].mask == constraint[1].mask)
