import json
from extxyz_kv_NB_grammar import ExtxyzKVGrammar

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
    
grammar = ExtxyzKVGrammar()
c_file, h_file = grammar.export_c()
with open('grammar.c', 'w') as cf:
    cf.write(c_file)
with open('grammar.h', 'w') as hf:
    hf.write(h_file)

import sys
test_line = sys.stdin.readline().strip()
result = grammar.parse(test_line)
parsed_part = result.tree.children[0].string
if test_line != parsed_part:
    print("Failed to parse entire input line, only '{}'".format(parsed_part))
    print("")

print(json.dumps(view_parse_tree(result), indent=2))
