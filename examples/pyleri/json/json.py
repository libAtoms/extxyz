'''JSON Grammar.'''
from pyleri import (
    Ref,
    Choice,
    Grammar,
    Regex,
    Keyword,
    Sequence,
    List)


class JsonGrammar(Grammar):
    START = Ref()

    # JSON strings should be enclosed in double quotes.
    # A backslash can be used as escape character.
    r_string = Regex(r'(")(?:(?=(\\?))\2.)*?\1')

    # JSON does not support floats or integers prefixed with a + sign
    # and floats must start with a number, for example .5 is not allowed
    # but should be written like 0.5
    r_float = Regex(r'-?[0-9]+\.?[0-9]+')
    r_integer = Regex('-?[0-9]+')

    k_true = Keyword('true')
    k_false = Keyword('false')
    k_null = Keyword('null')

    json_map_item = Sequence(r_string, ':', START)

    json_map = Sequence('{', List(json_map_item), '}')
    json_array = Sequence('[', List(START), ']')

    START = Choice(
        r_string,
        r_float,
        r_integer,
        k_true,
        k_false,
        k_null,
        json_map,
        json_array)
    
    
grammar = JsonGrammar()
    
c_file, h_file = grammar.export_c()

with open('grammar.c', 'w') as cf:
    cf.write(c_file)

with open('grammar.h', 'w') as hf:
    hf.write(h_file)    