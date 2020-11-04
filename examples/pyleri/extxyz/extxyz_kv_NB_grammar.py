'''extxyz key=value Grammar.'''
from pyleri import (
    Ref,
    Choice,
    Grammar,
    Regex,
    Keyword,
    Optional,
    Repeat,
    Sequence,
    List)

# This regex is defined outside grammar so it can be reused for extracting groups
properties_val_re = '([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+)'

class ExtxyzKVGrammar(Grammar):
    # string without quotes, some characters must be escaped 
    # <whitespace>='",}{][\
    r_barestring = Regex(r"""(?:[^\s='",}{\]\[\\]|(?:\\[\s='",}{\]\]\\]))+""")
    r_quotedstring = Regex(r'(")(?:(?=(\\?))\2.)*?\1')
    r_string = Choice(r_barestring, r_quotedstring)

    r_integer = Regex(r'[+-]?[0-9]+')
    r_float = Regex(r'[+-]?(?:[0-9]+[.]?[0-9]*|\.[0-9]+)(?:[dDeE][+-]?[0-9]+)?')

    k_true = Keyword('T')
    k_false = Keyword('F')

    ints = List(r_integer, mi=1)
    floats = List(r_float, mi=1)
    bools = List(Choice(k_true, k_false), mi=1)
    strings = List(r_string, mi=1)

    ints_sp = Repeat(r_integer, mi=1)
    floats_sp = Repeat(r_float, mi=1)
    bools_sp = Repeat(Choice(k_true, k_false), mi=1)
    strings_sp = Repeat(r_string, mi=1)

    old_one_d_array = Choice(Sequence('"', Choice(ints_sp, floats_sp, bools_sp), '"'),
                             Sequence('{', Choice(ints_sp, floats_sp, bools_sp, strings_sp), '}'))
    one_d_array = Sequence('[', Choice(ints, floats, strings, bools), ']')
    one_d_arrays = List(one_d_array, mi=1)
    two_d_array = Sequence('[', one_d_arrays, ']')

    key_item = Choice(r_string)

    val_item = Choice(
        r_integer,
        r_float,
        k_true,
        k_false,
        old_one_d_array,
        one_d_array,
        two_d_array,
        r_string)

    kv_pair = Sequence(key_item, '=', val_item, Regex(r'\s*'))
   
    properties_val_str = Regex(rf'^{properties_val_re}(:{properties_val_re})*')
    properties_kv_pair = Sequence(Keyword('Properties'), '=', properties_val_str, Regex(r'\s*'))
    
    old_float_array_9 = Sequence('"', Repeat(r_float, mi=9, ma=9), '"')
    old_float_array_3 = Sequence('"', Repeat(r_float, mi=3, ma=3), '"')
    float_array_3 = Sequence('[', List(r_float, mi=3, ma=3), ']')
    float_array_3x3 = Sequence('[', Repeat(float_array_3, mi=3, ma=3), ']')
    
    lattice_kv_pair = Sequence(Keyword('Lattice'), '=', Choice(old_float_array_9,
                                                               old_float_array_3,
                                                               float_array_3,
                                                               float_array_3x3), Regex(r'\s*'))
    
    all_kv_pair = Choice(properties_kv_pair, lattice_kv_pair, kv_pair, most_greedy=False)

    # can we encode that Lattice and Properties must both appear exactly once in the grammar?    
    START = Repeat(all_kv_pair)
