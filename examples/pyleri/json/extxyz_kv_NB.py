'''JSON Grammar.'''
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

import json

class JsonGrammar(Grammar):
    # string without quotes, some characters must be escaped 
    # <whitespace>='",}{][\
    r_barestring = Regex(r"""(?:[^\s='",}{\]\[\\]|(?:\\[\s='",}{\]\]\\]))+""")
    r_quotedstring = Regex(r'(")(?:(?=(\\?))\2.)*?\1')
    r_string = Choice(r_barestring, r_quotedstring)

    r_float = Regex(r'\b-?(?:[0-9]+(?:[dDeE][+-]?[0-9]+)|(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[dDeE][+-]?[0-9]+)?)\b')
    r_integer = Regex(r'\b-?[0-9]+\b')

    k_true = Keyword('T')
    k_false = Keyword('F')

    ints = List(r_integer)
    floats = List(r_float)
    bools = List(Choice(k_true, k_false))
    strings = List(r_string)

    ints_sp = List(r_integer, delimiter=Regex(r'\s+'), mi=1)
    floats_sp = List(r_float, delimiter=Regex(r'\s+'), mi=1)
    bools_sp = List(Choice(k_true, k_false), delimiter=Regex(r'\s+'), mi=1)
    strings_sp = List(r_string, delimiter=Regex(r'\s+'), mi=1)

    quoted_array = Sequence('"', Choice(ints_sp, floats_sp, bools_sp), '"')
    one_d_array_curly = Sequence('{', Choice(ints_sp, floats_sp, bools_sp, strings_sp), '}')
    one_d_array = Sequence('[', Choice(ints, floats, strings, bools), ']')
    two_d_array = Sequence('[', one_d_array, ']')

    key_item = Choice(r_string)

    val_item = Choice(
        r_float,
        r_integer,
        k_true,
        k_false,
        quoted_array,
        r_string,
        one_d_array_curly,
        one_d_array,
        two_d_array)

    kv_pair = Sequence(key_item, '=', val_item, Regex(r'\s*'))

    START = Repeat(kv_pair)

# Returns properties of a node object as a dictionary:
def node_props(node, children):
    return {
        'start': node.start,
        'end': node.end,
        'name': node.element.name if hasattr(node.element, 'name') else None,
        'element': node.element.__class__.__name__,
        'string': node.string,
        'children': children}


# Recursive method to get the children of a node object:
def get_children(children):
    return [node_props(c, get_children(c.children)) for c in children]


# View the parse tree:
def view_parse_tree(res):
    start = res.tree.children[0] \
        if res.tree.children else res.tree
    return node_props(start, get_children(start.children))    
    
grammar = JsonGrammar()
c_file, h_file = grammar.export_c()
with open('grammar.c', 'w') as cf:
    cf.write(c_file)
with open('grammar.h', 'w') as hf:
    hf.write(h_file)

import sys
test_json = sys.stdin.readline().strip()
# test_json = '{"Name": "Iris", "Age": 4, "test" : "bob \\""}'
result = grammar.parse(test_json)

print(json.dumps(view_parse_tree(result), indent=2))
