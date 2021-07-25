'''extxyz key=value Grammar.'''
from pyleri import (Ref, Choice, Grammar, Regex, Keyword, Optional,
                    Repeat, Sequence, List)

# These regexs are defined outside grammar so they can be reused
properties_val_re = '([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+)'
simplestring_re = r'\S+'
# any sequence surrounded by double quotes, with internal double quotes backslash escaped
dq_quotedstring_re = r'(")(?:(?=(\\?))\2.)*?\1'
cb_quotedstring_re = r'{(?:[^{}]|\\[{}])*(?<!\\)}'
sb_quotedstring_re = r'\[(?:[^\[\]]|\\[\[\]])*(?<!\\)\]'
# string without quotes, some characters must be escaped 
# <whitespace>=",}{][\
barestring_re = r"""(?:[^\s=",}{\]\[\\]|(?:\\[\s=",}{\]\[\\]))+"""
bare_int = r'(?:0|[1-9][0-9]*)'
# pieces of float regexp
opt_sign = r'[+-]?'
float_dec = r'(?:'+bare_int+r'\.|\.)[0-9]*'
exp = r'(?:[dDeE]'+opt_sign+r'[0-9]+)?'
# can't put \b at the end, because that won't match after non-word '.'
num_end = r'(?:\b|(?=\W)|$)'
float_re = opt_sign + r'(?:' + float_dec + exp + r'|' + bare_int + exp + r'|' + bare_int + r')' + num_end
# int can't have \b at the beginning, causes parser to not include sign as part of regexp match
# \b at end ensures that parser does not consider only initial digit of number as a complete match
integer_re = r'[+-]?'+bare_int+r'\b'
true_re =  r'\b(?:[tT]rue|TRUE|T)\b'
false_re = r'\b(?:[fF]alse|FALSE|F)\b'
bool_re = r'\b(?:[tT]rue|[fF]alse|TRUE|FALSE|[TF])\b'
whitespace_re = r'\s+'

# default output format strings
float_fmt = '%16.8f'
integer_fmt = '%8d'
string_fmt = '%s'
bool_fmt = '%.1s'

class ExtxyzKVGrammar(Grammar):
    r_barestring = Regex(barestring_re)
    r_dq_quotedstring = Regex(dq_quotedstring_re)
    r_cb_quotedstring = Regex(cb_quotedstring_re)
    r_sb_quotedstring = Regex(sb_quotedstring_re)
    r_string = Choice(r_barestring, r_dq_quotedstring, r_cb_quotedstring, r_sb_quotedstring)

    r_integer = Regex(integer_re)
    r_float = Regex(float_re)

    r_true = Regex(true_re)
    r_false = Regex(false_re)

    ints = List(r_integer, mi=1)
    floats = List(r_float, mi=1)
    bools = List(Choice(r_true, r_false), mi=1)
    strings = List(r_string, mi=1)

    ints_sp = Repeat(r_integer, mi=1)
    floats_sp = Repeat(r_float, mi=1)
    bools_sp = Repeat(Choice(r_true, r_false), mi=1)
    strings_sp = Repeat(r_string, mi=1)

    old_one_d_array = Choice(Sequence('"', Choice(ints_sp, ints, floats_sp, floats, bools_sp, bools), '"'),
                             Sequence('{', Choice(ints_sp, ints, floats_sp, floats, bools_sp, bools, strings_sp, strings), '}'))

    one_d_array_i = Sequence('[', ints, ']')
    one_d_array_f = Sequence('[', floats, ']')
    one_d_array_b = Sequence('[', bools, ']')
    one_d_array_s = Sequence('[', strings, ']')

    # one_d_arrays = List(one_d_array, mi=1)
    one_d_arrays = Choice(List(one_d_array_i, mi=1), List(one_d_array_f, mi=1),
                          List(one_d_array_b, mi=1), List(one_d_array_s, mi=1))

    two_d_array = Sequence('[', one_d_arrays, ']')

    key_item = Choice(r_string)

    val_item = Choice(
        r_integer,
        r_float,
        r_true,
        r_false,
        two_d_array,
        old_one_d_array,
        one_d_array_i,
        one_d_array_f,
        one_d_array_b,
        one_d_array_s,
        r_string)

    kv_pair = Sequence(key_item, '=', val_item, Regex(r'\s*'))
   
    properties = Keyword('Properties', ign_case=True)
    properties_val_str = Regex(rf'^{properties_val_re}(:{properties_val_re})*')
    properties_kv_pair = Sequence(properties, '=', 
                                  properties_val_str, Regex(r'\s*'))
    
    all_kv_pair = Choice(properties_kv_pair, kv_pair, most_greedy=False)

    START = Repeat(all_kv_pair)

def to_C_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

def write_grammar(dest_dir): 
    src, hdr = ExtxyzKVGrammar().export_c(target='extxyz_kv_grammar', c_indent=' ' * 4)
    with open(f'{dest_dir}/extxyz_kv_grammar.c', 'w') as fsrc, open(f'{dest_dir}/extxyz_kv_grammar.h', 'w') as fhdr:
        fsrc.write(src)
        fhdr.write(hdr)

        fhdr.write('\n')
        fhdr.write('#define WHITESPACE_RE ' + to_C_str(whitespace_re) + '\n')
        fhdr.write('#define SIMPLESTRING_RE ' + to_C_str(simplestring_re) + '\n')
        fhdr.write('#define INTEGER_RE ' + to_C_str(integer_re) + '\n')
        fhdr.write('#define FLOAT_RE ' + to_C_str(float_re) + '\n')
        fhdr.write('#define BOOL_RE ' + to_C_str(bool_re) + '\n')
        fhdr.write('\n')
        fhdr.write('#define INTEGER_FMT ' + to_C_str(integer_fmt) + '\n')
        fhdr.write('#define FLOAT_FMT ' + to_C_str(float_fmt) + '\n')
        fhdr.write('#define STRING_FMT ' + to_C_str(string_fmt) + '\n')
        fhdr.write('#define BOOL_FMT ' + to_C_str(bool_fmt) + '\n')

if __name__ == '__main__':
    import os
    write_grammar(os.getcwd())
