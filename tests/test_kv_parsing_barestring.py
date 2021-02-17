import re

def bare_string_strings():
    bare_strings = []

    # bare strings
    all_bare_str = ''
    for c in [chr(i) for i in range(32, 127)]:
        if re.search(r'\S', c) and c not in r'"=,\\][}{':
            all_bare_str += c
    bare_strings.append((all_bare_str, all_bare_str))

    for s in ['TRuE', '1.3k7', '-2.75e', '+2.75e-', '+2.75e+', '0012.1e-6']:
        bare_strings.append((s, s))

    return bare_strings

def test_bare_string_values(tmp_path, helpers):
    helpers.do_test_scalar(tmp_path, bare_string_strings(), single_elem_array_delims=['{}'])
