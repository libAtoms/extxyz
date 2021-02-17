from pathlib import Path

from extxyz.extxyz import read

kwargs_variants = [ { 'use_regex' : False, 'use_cextxyz' : False } ]

verbose = 0

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

def do_test_scalar(path, strings, old_one_d_array=True):
    for read_kwargs in kwargs_variants:
        print("Using kwargs", read_kwargs)
        for v, v_str in strings:
            # plain scalar
            do_test_config(path, 'scalar', v, 'scalar='+v_str, **read_kwargs)

            if old_one_d_array:
                # backward compat one-d array interpreted as a scalar
                for pre_sp in ['', ' ']:
                    for post_sp in ['', ' ']:
                        do_test_config(path, 'old_oned_scalar', v, 'old_oned_scalar="'+pre_sp+v_str+post_sp+'"', **read_kwargs)
                        do_test_config(path, 'old_oned_scalar', v, 'old_oned_scalar={'+pre_sp+v_str+post_sp+'}', **read_kwargs)

def integer_strings():
    ints = []
    for sign in ['', '+', '-']:
        for num in [ '2', '12' ]:
            ints.append((int(sign+num), sign+num))

    return ints

def test_integer_values(tmp_path):
    do_test_scalar(tmp_path, integer_strings())
 
def float_strings():
    floats = []

    for init_sign in ['', '+', '-']:
        for num in [ '1.0', '1.', '1', '12.0', '12', '0.12', '0.012', '.012']:
            f_str = float(init_sign+num)
            floats.append((f_str, init_sign+num))

            for exp_lett in ['e', 'E', 'd', 'D']:
                for exp_sign in ['', '+', '-']:
                    for exp_num in ['0', '2', '02', '12']:
                        f_val = float((init_sign+num+exp_lett+exp_sign+exp_num).replace('d','e').replace('D','e'))
                        floats.append((f_val, init_sign+num+exp_lett+exp_sign+exp_num))

    return floats

def test_float_values(tmp_path):
    do_test_scalar(tmp_path, float_strings())
 
# 
# # bool
# for b in ['T', 'true', 'True', 'TRUE', 'F', 'false', 'False', 'FALSE']:
#     b_str = b.startswith('t') or b.startswith('T')
#     print_config(f'tests_bool_{b_str}.xyz', 'b='+b)
# 
# # bare strings
# bare_strings = []
# all_bare_str = ''
# for c in [chr(i) for i in range(32, 127)]:
#     if re.search('\S', c) and c not in r'"=,\\][}{':
#         all_bare_str += c
# bare_strings += [all_bare_str]
# print_config(f'tests_barestring.xyz', 'bs='+all_bare_str)
# for s in ['TRuE', '1.3k7', '-2.75e', '+2.75e-', '+2.75e+', '0012.1e-6']:
#     bare_strings += [s]
#     print_config(f'tests_barestring.xyz', 'bs='+s)
# for s in bare_strings:
#     print_config(f'tests_barestring.xyz', 'bs = '+s)
#     print_config(f'tests_barestring.xyz', 'bs= '+s)
#     print_config(f'tests_barestring.xyz', 'bs ='+s)
# 
# # quoted strings
# for s in bare_strings:
#     print_config(f'tests_quotedstring.xyz', 'qs="'+s+'"')
# all_quoted_str = ''
# for c in [chr(i) for i in range(32, 127)]:
#     if re.search('\S', c):
#         if c == '"' or c == '\\':
#             all_quoted_str += '\\'
#         all_quoted_str += c
# print_config(f'tests_quotedstring.xyz', 'qs="'+all_quoted_str+'"')
# print_config(f'tests_quotedstring.xyz', 'qs="line one\\nline two"')
# print_config(f'tests_quotedstring_"a".xyz', 'qs="\\"a\\""')
# print_config(f'tests_quotedstring_a\\b.xyz', 'qs="a\\\\b"')
# print_config(f'tests_quotedstring_ab.xyz', 'qs="a\\b"')
# 
# # backward compat one-d arrays
# for seps in [ ('"', '"'), ('{', '}'), ('[', ']') ]:
#     ## integer
#     for l, f in [('1 2 3', 'integer'), ('1.0 2.0 3.0', 'float'), ('1 2.0 3', 'float'), ('1.0 2 3', 'float'), ('T F True FALSE', 'bool')]:
#         if seps[0] == '[':
#             print_config(f'tests_onedarray_{f}.xyz', 'i_a='+seps[0]+', '.join(l.split())+seps[1])
#         else:
#             print_config(f'tests_onedarray_{f}.xyz', 'i_a='+seps[0]+l+seps[1])
# 
# # one-d array of string, only new style  
# for l in [ ' "a", "b" ', ' a, b ', 'a,b', '"a","b"', ' a, "b", "c" ', ' a, "b", c ', 
#            ' "a", b, c ', ' "a", b, "c" ', ' "a, b", "c]" ', ' T, F, bob ', ' T, F, "bob" ', 
#            ' T, F, bob, TRUE ', ' T, F, "bob", TRUE ' ]:
#     print_config('tests_onedarray_string.xyz', 's_a=['+l+']')
# 
# # two d array, only new style
# print_config('tests_twodarray_integer.xyz', 'i_aa=[ [ 1, 2 ] ]')
# print_config('tests_twodarray_integer.xyz', 'i_aa=[ [ 1, 2 ], [ 3, 4 ] ]')
# print_config('tests_twodarray_float.xyz', 'f_aa=[ [ 1.0, 2.2 ] ]')
# print_config('tests_twodarray_float.xyz', 'f_aa=[ [ 1.1, 2.0 ], [ -3.2, 4.5 ] ]')
# print_config('tests_twodarray_float.xyz', 'f_aa=[ [ 1, 2 ], [ -3.2, 4.5 ] ]')
# print_config('tests_twodarray_bool.xyz', 'b_aa=[ [ T, F ] ]')
# print_config('tests_twodarray_bool.xyz', 'b_aa=[ [ F, False ], [ TRUE, true ] ]')
# print_config('tests_twodarray_string.xyz', 's_aa=[ [ a, b, bob, "joe", sam, "end" ] ]')
# print_config('tests_twodarray_string.xyz', 's_aa=[ [ a, "joe" ], [ "b", sam ] ]')
# print_config('tests_twodarray_string.xyz', 's_aa=[ [ a, joe ], [ "b", "sam" ] ]')
# print_config('tests_twodarray_string.xyz', 's_aa=[ [ "a", "joe" ], [ b, sam ] ]')
# print_config('tests_twodarray_string.xyz', 's_aa=[ [ T, F ], [ b, sam ] ]')
# print_config('tests_twodarray_string.xyz', 's_aa=[ [ 12, -5 ], [ b, sam ] ]')
# print_config('tests_twodarray_string.xyz', 's_aa=[ [ T, FALSE], [ 12, -5 ], [ b, sam ], [ "a", "joe"] ]')
# 
# for l_i, l in enumerate(['i 5', 'i_a [2, 3]']):
#     print_config(f'tests_fail_no_equals_{l_i}.xyz', l)
# 
# for c_i, c in enumerate('"=,\[]{} '):
#     print_config(f'tests_fail_barestring_{c_i}.xyz', 's=abc'+c+'def')
# 
# for l_i, l in enumerate(["'abc'", "\"abc'", "\"abc\\\"def"]):
#     print_config(f'tests_fail_quotedstring_{l_i}.xyz', 's='+l)
# 
# for l_i, l in enumerate(['"1, 2}', '{1, 2"', '[1, 2, ]', '[ , 2, 3]']):
#     print_config(f'tests_fail_onedarray_{l_i}.xyz', 's='+l)
# 
# for l_i, l in enumerate(['[ [ 1, 2], [ 3 ] ]', '[ [ 1, 2 ] [ 1, 2 ] ]']):
#     print_config(f'tests_fail_twodarray_{l_i}.xyz', 's='+l)
