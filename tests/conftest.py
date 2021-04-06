import pytest
import os

from pathlib import Path
import numpy as np

from extxyz.extxyz import read

verbose = 0

if 'USE_CEXTXYZ' in os.environ:
    kwargs_variants = [ { 'use_regex' : False, 'use_cextxyz' : os.environ['USE_CEXTXYZ'].startswith('t') or os.environ['USE_CEXTXYZ'].startswith('T') } ]
else:
    kwargs_variants = [ { 'use_regex' : False, 'use_cextxyz' : False },
                        { 'use_regex' : False, 'use_cextxyz' : True  } ]



class Helpers:
    @staticmethod
    def read_all_variants(filename):
        ats_variants = []
        for read_kwargs in kwargs_variants:
            ats_variants.append(read(filename, verbose=verbose, **read_kwargs))
        return ats_variants


    @staticmethod
    def do_test_kv_pair(path, key, val, kv_str):
        for read_kwargs in kwargs_variants:
            with open(path / Path('test_file.extxyz'), 'w') as fout:
                fout.write(f'1\nProperties=species:S:1:pos:R:3 Lattice="1 0 0  0 1 0   0 0 1" {kv_str}\nSi 0.0 0.0 0.0\n')

            # if verbose != 0:
            with open(path / Path('test_file.extxyz')) as fin:
                print(''.join(fin.readlines()))

            at = read(str(path / Path('test_file.extxyz')), verbose=verbose, **read_kwargs)

            assert np.all(at.info[key] == val)


    @staticmethod
    def do_test_scalar(path, strings, is_string=False):
        for v, v_str in strings:
            # plain scalar
            Helpers.do_test_kv_pair(path, 'scalar', v, 'scalar='+v_str)

            if is_string:
                single_elem_array_delims = ['{}']
            else:
                single_elem_array_delims = ['{}', '""']
            for delims in single_elem_array_delims:
                # backward compat one-d array interpreted as a scalar
                for pre_sp in ['', ' ']:
                    for post_sp in ['', ' ']:
                        Helpers.do_test_kv_pair(path, 'old_oned_scalar', v,
                            'old_oned_scalar=' + delims[0] + pre_sp + v_str + post_sp + delims[1])


    @staticmethod
    def do_one_d_variants(path, is_string, n, v_array, v_str_array):
        if is_string:
            delimsep=[('[',']',',', 1), ('{','}',' ', 2)]
        else:
            delimsep=[('[',']',',', 1), ('{','}',' ', 2), ('"', '"', ' ', 2)]

        for do, dc, ds, min_n in delimsep:
            if n >= min_n:
                for global_pre_sp in ['', ' ']:
                    for global_post_sp in ['', ' ']:
                        for pre_sp in ['', ' ']:
                            for post_sp in ['', ' ']:
                                v_str = v_str_array[0]
                                if n > 2:
                                    v_str += ds + ds.join([pre_sp + v_str_array[i] + post_sp for i in range(1,n-1)])
                                if n > 1:
                                    v_str += ds + pre_sp + v_str_array[-1]
                                Helpers.do_test_kv_pair(path, 'array', v_array,
                                    'array=' + do + global_pre_sp + v_str + global_post_sp + dc)


    @staticmethod
    def do_test_one_d_array(path, strings, ns=None, is_string=False):
        if ns is None:
            ns = [1, 2, 3, 7, -10]

        for n in ns:
            if n > 0:
                for v, v_str in strings:
                    Helpers.do_one_d_variants(path, is_string, n, [v]*n, [v_str]*n)
            else:
                ntot = np.abs(n)
                selected_inds = np.random.choice(list(range(len(strings))), ntot, replace=(ntot > len(strings)))
                selected  = [strings[i] for i in selected_inds]
                Helpers.do_one_d_variants(path, is_string, ntot, [s[0] for s in selected], [s[1] for s in selected])


    @staticmethod
    def do_two_d_variants(path, nrow, ncol, v_array, v_str_array):
        for global_pre_sp in ['', ' ']:
            for global_post_sp in ['', ' ']:
                for pre_sp in ['', ' ']:
                    for post_sp in ['', ' ']:
                        v_array = np.asarray(v_array).reshape(nrow, ncol)

                        v_str = '['
                        i=0
                        for row in range(nrow):
                            v_str += global_pre_sp + '[' + global_pre_sp + v_str_array[i]
                            i += 1
                            for col in range(1, ncol-1):
                                v_str += post_sp + ',' + pre_sp + v_str_array[i]
                                i += 1
                            if ncol > 1:
                                v_str += post_sp + ',' + pre_sp + v_str_array[i]
                                i += 1
                            v_str += global_post_sp + ']'
                            if row < nrow-1:
                                v_str += global_post_sp + ',' + global_pre_sp
                        v_str += global_post_sp + ']'

                        Helpers.do_test_kv_pair(path, 'array', v_array,
                            'array=' + v_str)


    @staticmethod
    def do_test_two_d_array(path, strings, ns=None):
        if ns is None:
            ns = [(1,1), (1,3), (3,1), (3,3), (-5,-5)]

            for nrow, ncol in ns:
                if nrow > 0:
                    for v, v_str in strings:
                        Helpers.do_two_d_variants(path, nrow, ncol, [v] * nrow*ncol, [v_str] * nrow*ncol)
                else:
                    ntot = np.abs(nrow) * np.abs(ncol)
                    selected_inds = np.random.choice(list(range(len(strings))), ntot, replace=(ntot > len(strings)))
                    selected  = [strings[i] for i in selected_inds]
                    Helpers.do_two_d_variants(path, np.abs(nrow), np.abs(ncol), [s[0] for s in selected], [s[1] for s in selected])


@pytest.fixture
def helpers():
    return Helpers

