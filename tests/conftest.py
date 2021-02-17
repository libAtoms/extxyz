import pytest

from pathlib import Path
from extxyz.extxyz import read

verbose = 0

kwargs_variants = [ { 'use_regex' : False, 'use_cextxyz' : False } ]

class Helpers:
    @staticmethod
    def do_test_config(path, key, val, kv_str, **read_kwargs):
        with open(path / Path('test_file.extxyz'), 'w') as fout:
            fout.write(f'1\nProperties=species:S:1:pos:R:3 Lattice="1 0 0  0 1 0   0 0 1" {kv_str}\nSi 0.0 0.0 0.0\n')

        if verbose > 0:
            with open(path / Path('test_file.extxyz')) as fin:
                print(''.join(fin.readlines()))

        at = read(str(path / Path('test_file.extxyz')), verbose=verbose, **read_kwargs)

        if at.info[key] != val:
            print("got info", at.info, val)
            with open(path / Path('test_file.extxyz')) as fin:
                print(''.join(fin.readlines()))
        assert at.info[key] == val


    @staticmethod
    def do_test_scalar(path, strings, old_one_d_array=True):
        for read_kwargs in kwargs_variants:
            print("Using kwargs", read_kwargs)
            for v, v_str in strings:
                # plain scalar
                Helpers.do_test_config(path, 'scalar', v, 'scalar='+v_str, **read_kwargs)

                if old_one_d_array:
                    # backward compat one-d array interpreted as a scalar
                    for pre_sp in ['', ' ']:
                        for post_sp in ['', ' ']:
                            Helpers.do_test_config(path, 'old_oned_scalar', v, 'old_oned_scalar="'+pre_sp+v_str+post_sp+'"', **read_kwargs)
                            Helpers.do_test_config(path, 'old_oned_scalar', v, 'old_oned_scalar={'+pre_sp+v_str+post_sp+'}', **read_kwargs)



@pytest.fixture
def helpers():
    return Helpers

