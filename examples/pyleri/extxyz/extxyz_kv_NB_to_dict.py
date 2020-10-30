import sys
import json
import numpy as np

from extxyz_kv_NB_grammar import ExtxyzKVGrammar

# def print_names(ls):
    # for l_i, l in enumerate(ls):
        # if hasattr(l, "element") and hasattr(l.element, "name"):
            # print(l_i, "name", l.element.name, "string", l.string)
        # else:
            # print(l_i, "name", "None", "string", l.string)

def AST_to_dict(result):
    dict_out = {}
    top = result.tree.children[0]
    for kv_pair in top.children:
        # right type
        assert kv_pair.element.name == 'kv_pair'
        # key, =, val, optional whitespace
        assert len(kv_pair.children) in (3,4)
        # = token
        assert kv_pair.children[1].string == '='

        key = kv_pair.children[0].string
        value = kv_pair.children[2].children[0]
        # print("key", key, "val elem name", value.element.name)
        if 'one_d_array' in value.element.name:
            if value.element.name == 'one_d_array':
                # should be [, items, ]
                assert len(value.children) == 3
                # should be Choice of types
                assert len(value.children[1].children) == 1
                value = value.children[1].children[0]
                value_name = value.element.name
                items = [item.string for item in value.children[0::2]]
            else:
                # should be a choice of quoted vs. curly
                assert len(value.children) == 1
                # old_on_d_array, children 0 and 2 should be " or {}
                assert len(value.children[0].children) == 3
                # should be a Choice of types
                assert len(value.children[0].children[1].children) == 1
                value = value.children[0].children[1].children[0]
                value_name = value.element.name
                items = [item.string for item in value.children]
            # print("got 1-d array", value_name, items)
            if value_name.startswith('ints'):
                value = np.asarray([int(i) for i in items])
            elif  value_name.startswith('floats'):
                value = np.asarray([float(i) for i in items])
            elif value_name.startswith('bools'):
                value = np.asarray([i == 'T' for i in items])
            elif value_name.startswith('strings'):
                value = np.asarray(items)
            else:
                raise RuntimeError(f'unknown type of 1-d array contents {value_name}')
        elif value.element.name == 'two_d_array':
            raise RuntimeError('two_d_array not implemented yet')
        elif value.element.name == 'r_string':
            value = value.string
        elif value.element.name == 'r_integer':
            value = int(value.string)
        elif value.element.name == 'r_float':
            value = float(value.string)
        elif value.element.name == 'k_true':
            value = True
        elif value.element.name == 'k_false':
            value = False
        else:
            raise RuntimeError(f'unknown type of scalar {value.element.name}')
        # print("final key", key, "value", value)
        dict_out[key] = value

    return dict_out

if __name__ == '__main__':
    grammar = ExtxyzKVGrammar()

    test_line = sys.stdin.readline().strip()
    result = grammar.parse(test_line)

    parsed_part = result.tree.children[0].string
    if test_line != parsed_part:
        print("Failed to parse entire input line, only '{}'".format(parsed_part))
        print("")

    json.dump({ k : v.tolist() if hasattr(v, 'tolist') else v for k, v in AST_to_dict(result).items()}, sys.stdout)
    sys.stdout.write('\n')
