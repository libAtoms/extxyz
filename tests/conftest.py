import pytest

from pathlib import Path
from extxyz.extxyz import read

verbose = 0

kwargs_variants = [ { 'use_regex' : False, 'use_cextxyz' : False },
                    { 'use_regex' : False, 'use_cextxyz' : True  } ]

class Helpers:
    @staticmethod
    def do_test_config(path, key, val, kv_str, **read_kwargs):
        with open(path / Path('test_file.extxyz'), 'w') as fout:
            fout.write(f'1\nProperties=species:S:1:pos:R:3 Lattice="1 0 0  0 1 0   0 0 1" {kv_str}\nSi 0.0 0.0 0.0\n')

        # if verbose != 0:
        with open(path / Path('test_file.extxyz')) as fin:
            print(''.join(fin.readlines()))

        at = read(str(path / Path('test_file.extxyz')), verbose=verbose, **read_kwargs)

        print(key, val, 'at.info', at.info)

        if not isinstance(val, str):
            # check for iterable
            try:
                # will work only if iterable
                for vi, v in zip(at.info[key], val):
                    assert vi == v
            except TypeError:
                # not iterable
                assert at.info[key] == val
        else:
            assert at.info[key] == val


    @staticmethod
    def do_test_scalar(path, strings, is_string=False):
        for read_kwargs in kwargs_variants:
            print("Using kwargs", read_kwargs)
            for v, v_str in strings:
                # plain scalar
                Helpers.do_test_config(path, 'scalar', v, 'scalar='+v_str, **read_kwargs)

                if is_string:
                    single_elem_array_delims = ['{}']
                else:
                    single_elem_array_delims = ['{}', '""']
                for delims in single_elem_array_delims:
                    # backward compat one-d array interpreted as a scalar
                    for pre_sp in ['', ' ']:
                        for post_sp in ['', ' ']:
                            Helpers.do_test_config(path, 'old_oned_scalar', v,
                                'old_oned_scalar=' + delims[0] + pre_sp + v_str + post_sp + delims[1],
                                **read_kwargs)


    @staticmethod
    def do_test_one_d_array(path, strings, ns=None, is_string=False):
        if is_string:
            delimsep=[('[',']',',', 1), ('{','}',' ', 2)]
        else:
            delimsep=[('[',']',',', 1), ('{','}',' ', 2), ('"', '"', ' ', 2)]

        if ns is None:
            ns = [1,2,3,7]

        for n in ns:
            for read_kwargs in kwargs_variants:
                for v, v_str in strings:
                    # new style
                    for do, dc, ds, min_n in delimsep:
                        if n >= min_n:
                            for global_pre_sp in ['', ' ']:
                                for global_post_sp in ['', ' ']:
                                    for pre_sp in ['', ' ']:
                                        for post_sp in ['', ' ']:
                                            v_array = [v]*n
                                            v_str_array = v_str
                                            if n > 2:
                                                v_str_array += ds + ds.join([pre_sp + v_str + post_sp]*(n-2))
                                            if n > 1:
                                                v_str_array += ds + pre_sp + v_str
                                            Helpers.do_test_config(path, 'array', v_array,
                                                'array=' + do + global_pre_sp + v_str_array + global_post_sp + dc,
                                                **read_kwargs)


@pytest.fixture
def helpers():
    return Helpers

