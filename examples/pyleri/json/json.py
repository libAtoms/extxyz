'''JSON Grammar.'''
from pyleri import (
    Ref,
    Choice,
    Grammar,
    Regex,
    Keyword,
    Sequence,
    List)

import json

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
    
test_json = '{"Name": "Iris", "Age": 4}'
result = grammar.parse(test_json)

print(json.dumps(view_parse_tree(result), indent=2))