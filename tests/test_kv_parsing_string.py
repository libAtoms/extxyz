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

def test_quoted_string_values(tmp_path, helpers):
    bare_strings = bare_string_strings()
    print("bare_strings", bare_strings)
    quoted_strings = [(c[0], '"'+c[1]+'"') for c in bare_strings]
    print("quoted_strings", quoted_strings)

    def quote_string(string):
        quoted_string = string.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        return string, '"' + quoted_string + '"'

    all_nonwhitespace = ''.join([chr(c) for c in range(32,127) if re.search(r'\S', chr(c))])
    quoted_strings.append(quote_string(all_nonwhitespace))

    # various special escaped things: newline, internal matching quotes, and literal backslash
    for string in [ 'line one\nline two', '"a"', 'a\\b' ]:
        quoted_strings.append(quote_string(string))

    # backslash escape of a non-special character, which is just literally that character 
    quoted_strings.append(('ab', '"a\\b"'))

    helpers.do_test_scalar(tmp_path, quoted_strings, single_elem_array_delims=['{}'])
