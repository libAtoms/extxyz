'''extxyz key=value Grammar.'''
from pyleri import (Ref, Choice, Grammar, Regex, Keyword, Optional,
                    Repeat, Sequence, List)

# These regexs are defined outside grammar so they can be reused
properties_val_re = '([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+)'
simplestring_re = r'\S+'
# any sequence surrounded by double quotes, with internal double quotes backslash escaped
quotedstring_re = r'(")(?:(?=(\\?))\2.)*?\1'
# string without quotes, some characters must be escaped 
# <whitespace>=",}{][\
barestring_re = r"""(?:[^\s=",}{\]\[\\]|(?:\\[\s=",}{\]\[\\]))+"""
bare_int = r'(?:[0-9]|[1-9][0-9]+)'
float_re = r'[+-]?(?:'+bare_int+'[.]?[0-9]*|\.[0-9]+)(?:[dDeE][+-]?[0-9]+)?'
integer_re = r'[+-]?'+bare_int
true_re =  r'(?:[tT]rue|TRUE|T)'
false_re = r'(?:[fF]alse|FALSE|F)'
bool_re = r'(?:[tT]rue|[fF]alse|TRUE|FALSE|[TF])'
whitespace_re = r'\s+'

class ExtxyzKVGrammar(Grammar):
    r_barestring = Regex(barestring_re)
    r_quotedstring = Regex(quotedstring_re)
    r_string = Choice(r_barestring, r_quotedstring)

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

    old_one_d_array = Choice(Sequence('"', Choice(ints_sp, floats_sp, bools_sp), '"'),
                             Sequence('{', Choice(ints_sp, floats_sp, bools_sp, strings_sp), '}'))

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
        old_one_d_array,
        one_d_array_i,
        one_d_array_f,
        one_d_array_b,
        one_d_array_s,
        two_d_array,
        r_string)

    kv_pair = Sequence(key_item, '=', val_item, Regex(r'\s*'))
   
    properties = Keyword('Properties', ign_case=True)
    properties_val_str = Regex(rf'^{properties_val_re}(:{properties_val_re})*')
    properties_kv_pair = Sequence(properties, '=', 
                                  properties_val_str, Regex(r'\s*'))
    
    all_kv_pair = Choice(properties_kv_pair, kv_pair, most_greedy=False)

    START = Repeat(all_kv_pair)

if __name__ == '__main__':
    src, hdr = ExtxyzKVGrammar().export_c( target='extxyz_kv_grammar', c_indent=' ' * 4)
    with open('extxyz_kv_grammar.c', 'w') as fsrc, open('extxyz_kv_grammar.h', 'w') as fhdr:
        fsrc.write(src)
        fhdr.write(hdr)
