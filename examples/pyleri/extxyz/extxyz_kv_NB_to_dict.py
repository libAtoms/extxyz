import sys
import json
import numpy as np

from extxyz_kv_NB_grammar import ExtxyzKVGrammar

def print_names(ls):
    for l_i, l in enumerate(ls):
        if hasattr(l, "element") and hasattr(l.element, "name"):
            print(l_i, "name", l.element.name, "string", l.string)
        else:
            print(l_i, "name", "None", "string", l.string)

def parse_one_d_array(value):
    # should be [, items, ]
    assert len(value.children) == 3
    # should be Choice of types
    assert len(value.children[1].children) == 1

    value = value.children[1].children[0]
    value_name = value.element.name
    # every other value is a delimiter
    items = [item.string for item in value.children[0::2]]

    return value_name, items

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
                value_name, items = parse_one_d_array(value)
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
                value = np.asarray([int(i) for i in items], dtype=int)
            elif  value_name.startswith('floats'):
                value = np.asarray([float(i) for i in items], dtype=float)
            elif value_name.startswith('bools'):
                value = np.asarray([i == 'T' for i in items], dtype=bool)
            elif value_name.startswith('strings'):
                value = np.asarray(items, dtype=str)
            else:
                raise RuntimeError(f'unknown type of 1-d array contents {value_name}')
        elif value.element.name == 'two_d_array':
            # should be [, one_d_arrays, ]
            assert len(value.children) == 3

            # every other value is a delimiter
            value_names = []
            items = []
            for oda in value.children[1].children[0::2]:
                l_value_name, l_items = parse_one_d_array(oda)
                value_names.append(l_value_name)
                items.append(l_items)
            value_names = np.asarray(value_names)
            if all(value_names == 'ints'):
                value = np.asarray(items, dtype=int)
            elif all(np.logical_or(value_names == 'ints', value_names == 'floats')):
                value = np.asarray(items, dtype=float)
            elif all(value_names == 'bools'):
                value = np.asarray(items, dtype=bool)
            elif all(value_names == 'strings'):
                value = np.asarray(items, dtype=str)
            else:
                raise RuntimeError(f'Got mix of types that cannot be automatically promoted {value_names}')
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

    d = AST_to_dict(result)
    for (k, v) in d.items():
        print(k, "ndarray({})".format(v.dtype) if isinstance(v, np.ndarray) else type(v), v)
    json.dump({ k : v.tolist() if hasattr(v, 'tolist') else v for k, v in d.items()}, sys.stdout)
    sys.stdout.write('\n')
