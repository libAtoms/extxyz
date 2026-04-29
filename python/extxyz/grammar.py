"""Pure-Python parser AST machinery + the ``Properties`` column descriptor.

This module has no ASE dependency. It is shared between the dict-based
core (``extxyz.core``) and the ``ase-extxyz`` plugin package.
"""
import functools
import json
import re

import numpy as np
from pyleri.node import Node

from .extxyz_kv_grammar import (ExtxyzKVGrammar,
                                float_re, integer_re, bool_re, simplestring_re,
                                whitespace_re,
                                integer_fmt, float_fmt, string_fmt, bool_fmt)


# Singleton grammar — building it is non-trivial.
grammar = ExtxyzKVGrammar()


class NodeVisitor:
    """
    Implementation of the Visitor pattern for a pyleri parse tree. Walks the
    tree calling a visitor function for every node found. The visitor methods
    should be defined in subclasses as ``visit_`` plus either (1) the name, or
    (2) the class name of the element, e.g. ``visit_floats`` or ``visit_Regex``.
    If no visitor function is found, the ``generic_visit`` visitor is used.
    """

    def visit(self, node):
        if isinstance(node, Node):
            if hasattr(node.element, 'name'):
                method = 'visit_' + node.element.name
                if not hasattr(self, method):
                    method = 'visit_' + node.element.__class__.__name__
            else:
                method = 'visit_' + node.element.__class__.__name__
        else:
            method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        children = getattr(node, 'children', [])
        for child in children:
            self.visit(child)


class NodeTransformer(NodeVisitor):
    """Subclass of ``NodeVisitor`` that allows the tree to be modified."""

    def generic_visit(self, node):
        children = getattr(node, 'children', [])
        new_children = []
        for child in children:
            child = self.visit(child)
            if child is None:
                continue
            elif isinstance(child, list):
                new_children.extend(child)
                continue
            new_children.append(child)
        if hasattr(node, 'children'):
            node.children[:] = new_children
        else:
            node.children = new_children
        return node


class TreeDumper(NodeVisitor):
    """Diagnostic visitor that prints a textual representation of the parse tree."""

    def __init__(self, prefix=''):
        self.depth = 0
        self.prefix = prefix

    def generic_visit(self, node):
        if isinstance(node, Node):
            name = getattr(node.element, 'name', None)
            str_repr = (f'{node.element.__class__.__name__}'
                        f'(name={name}, string="{node.string}")')
        else:
            str_repr = str(node)

        print(self.prefix + '  ' * self.depth + str_repr)
        self.depth += 1
        super().generic_visit(node)
        self.depth -= 1


class TreeCleaner(NodeTransformer):
    def visit_Token(self, node):
        return None

    def visit_Choice(self, node):
        child = node.children[0]
        if getattr(child.element, 'name', None) is None:
            child.element.name = node.element.name
        return self.visit(child)

    def visit_Regex(self, node):
        if not hasattr(node.element, 'name'):
            return None
        return self.generic_visit(node)


class Value:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f'Value({repr(self.value)})'


class ExtractValues(NodeTransformer):
    """Convert scalars and lists of floats/ints/strings/bools to Python types."""

    tf = {'r_true': True, 'r_false': False}

    def visit_properties(self, node):
        return Value(node.element.name)

    def visit_r_barestring(self, node):
        return Value(node.string)

    @staticmethod
    def clean_qs(string):
        # remove initial and final quotes
        string = string[1:-1]
        # replace escaped newline
        string = string.replace('\\n', '\n')
        # replace everything else as escaped literal
        string = re.sub(r'\\(.)', r'\1', string)
        return string

    def visit_r_quotedstring(self, node):
        return Value(ExtractValues.clean_qs(node.string))

    visit_r_dq_quotedstring = visit_r_quotedstring
    visit_r_cb_quotedstring = visit_r_quotedstring
    visit_r_sb_quotedstring = visit_r_quotedstring

    def visit_r_float(self, node):
        return Value(float(node.string.replace('d', 'e').replace('D', 'e')))

    def visit_r_integer(self, node):
        return Value(int(node.string))

    def visit_r_true(self, node):
        return Value(ExtractValues.tf[node.element.name])

    visit_r_false = visit_r_true

    def visit_strings(self, node):
        return Value([c.string if '_quotedstring' not in c.element.name
                      else ExtractValues.clean_qs(c.string) for c in node.children])

    visit_strings_sp = visit_strings

    def visit_ints(self, node):
        return Value([int(c.string) for c in node.children])

    visit_ints_sp = visit_ints

    def visit_floats(self, node):
        return Value([float(c.string.replace('d', 'e').replace('D', 'e')) for c in node.children])

    visit_floats_sp = visit_floats

    def visit_bools(self, node):
        return Value([ExtractValues.tf[c.element.name] for c in node.children])

    visit_bools_sp = visit_bools

    def visit_properties_val_str(self, node):
        return Value(node.string)


class OneDimArrays(NodeTransformer):
    """Convert one-dimensional arrays to numpy arrays."""

    def visit_one_d_array(self, node):
        assert len(node.children) == 1
        return Value(np.array(node.children[0].value))

    visit_one_d_array_i = visit_one_d_array
    visit_one_d_array_f = visit_one_d_array
    visit_one_d_array_b = visit_one_d_array
    visit_one_d_array_s = visit_one_d_array

    def visit_old_one_d_array(self, node):
        result = self.visit_one_d_array(node)
        if result.value.shape == (9,):
            result.value = result.value.reshape((3, 3), order='F')
        elif result.value.shape == (1,):
            # old array with one column is just a scalar
            result.value = result.value.item()
        return result


class OneDimToTwoDim(NodeTransformer):
    """Combine one-dimensional arrays to form two-dimensional arrays."""

    def visit_one_d_arrays(self, node):
        return Value(np.array([c.value for c in node.children]))


class TwoDimArrays(NodeTransformer):
    def visit_two_d_array(self, node):
        assert len(node.children) == 1
        return Value(node.children[0].value)


def result_to_dict(result, verbose=0):
    """Convert from pyleri parse result to key/value info dictionary."""
    tree = result.tree.children[0]
    if verbose >= 1:
        print('input tree:')
        TreeDumper('input').visit(tree)
    tree = TreeCleaner().visit(tree)
    if verbose >= 3:
        print('cleaned tree:')
        TreeDumper('cleaned').visit(tree)
    tree = ExtractValues().visit(tree)
    if verbose >= 2:
        print('cleaned and extracted tree:')
        TreeDumper('extracted').visit(tree)
    tree = OneDimArrays().visit(tree)
    tree = OneDimToTwoDim().visit(tree)
    tree = TwoDimArrays().visit(tree)
    if verbose >= 1:
        print('final tree:')
        TreeDumper('final').visit(tree)

    result_dict = {}
    for (key, value) in [node.children for node in tree.children]:
        if key.value in result_dict:
            raise KeyError(f'duplicate key {key.value}')
        if not isinstance(value, Value):
            raise ValueError(f'unsupported value {value}, key {key.value}')
        result_dict[key.value] = value.value
    return result_dict


class Properties:
    """Per-atom column descriptor parsed from the ``Properties=…`` comment-line key.

    No ASE awareness. ``ase-extxyz`` provides the ``Atoms``-aware
    ``Properties.from_atoms`` equivalent as a free function in its ``io.py``.
    """

    per_atom_dtype = {'R': float,
                      'I': int,
                      'S': 'U10',  # FIXME: can we avoid fixed string length?
                      'L': bool}

    # map from numpy dtype.kind to extxyz property type
    format_map = {'d': 'R',
                  'f': 'R',
                  'i': 'I',
                  'O': 'S',
                  'S': 'S',
                  'U': 'S'}

    # regular expressions for data columns, imported from grammar definition
    per_atom_column_re = {
        'R': float_re,
        'I': integer_re,
        'S': simplestring_re,
        'L': bool_re,
    }

    default_format_dict = {
        'R': float_fmt,
        'I': integer_fmt,
        'S': string_fmt,
        'L': bool_fmt,
    }

    def __init__(self, property_string=None, properties=None,
                 format_dict=None, data=None):
        if (property_string is None) + (properties is None) != 1:
            raise ValueError('exactly one of property_string and properties '
                             f'should be present; got {property_string} and '
                             f'{properties} respectively.')

        if property_string:
            items = property_string.split(':')
            items = [items[3 * i:3 * i + 3] for i in range(len(items) // 3)]
            self.properties = [(prop[0], prop[1], int(prop[2])) for prop in items]
        else:
            self.properties = properties

        if format_dict is None:
            format_dict = Properties.default_format_dict
        self.format_dict = format_dict
        self._data = data

    def __iter__(self):
        for (name, _, _) in self.properties:
            yield name

    def get_dtype(self, scalar=True):
        """Construct numpy dtypes from property definitions."""
        dtype_scalar = []
        dtype_vector = []
        for (name, property_type, cols) in self.properties:
            if cols == 1:
                for dtype in (dtype_scalar, dtype_vector):
                    dtype.append((name, Properties.per_atom_dtype[property_type]))
            else:
                for col in range(cols):
                    dtype_scalar.append((f'{name}{col}',
                                         Properties.per_atom_dtype[property_type]))
                dtype_vector.append((name,
                                     Properties.per_atom_dtype[property_type], (cols,)))
        return np.dtype(dtype_scalar) if scalar else np.dtype(dtype_vector)

    @functools.cached_property
    def dtype_scalar(self):
        return self.get_dtype(scalar=True)

    @functools.cached_property
    def dtype_vector(self):
        return self.get_dtype(scalar=False)

    @functools.cached_property
    def regex(self):
        regex = r'^\s*'
        for (_, property_type, cols) in self.properties:
            this_regex = '(' + Properties.per_atom_column_re[property_type] + ')' + whitespace_re
            for _col in range(cols):
                regex += this_regex
        regex = re.sub('.' * len(whitespace_re) + '$', '', regex)
        regex = re.compile(regex, flags=re.M)
        return regex

    @functools.cached_property
    def property_string(self):
        return ':'.join(f'{name}:{ptype}:{cols}' for (name, ptype, cols) in self.properties)

    @functools.cached_property
    def format_strings(self):
        out = []
        for (_, property_type, ncols) in self.properties:
            fmt = self.format_dict[property_type]
            out.extend([fmt] * ncols)
        return out

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        self._data = np.atleast_1d(data.view(self.dtype_vector))

    @property
    def data_columns(self):
        return self._data.view(self.dtype_scalar)


# ----------------------------------------------------------------------------
# Encoding helpers — comment-line value formatting
# ----------------------------------------------------------------------------

def escape(string):
    have_special = (' ' in string or '=' in string or '"' in string or
                    ',' in string or '[' in string or ']' in string or
                    '{' in string or '}' in string or '\\' in string or '\n' in string)
    out_string = ''
    for c in string:
        if c == '\n':
            out_string += '\\n'
        elif c == '\\' or c == '"':
            out_string += '\\' + c
        else:
            out_string += c
    if have_special:
        out_string = f'"{out_string}"'
    return out_string


def _tf(x):
    return '@@T@@' if x else '@@F@@'


_tf_vec = np.vectorize(_tf)


class ExtXYZEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            if obj.dtype.kind == 'b':
                obj = _tf_vec(obj)
            return obj.tolist()
        elif isinstance(obj, bool):
            return _tf(obj)
        return super().default(obj)


def extxyz_value_to_string(value):
    if isinstance(value, str):
        return escape(value)
    string = ExtXYZEncoder().encode(value)
    return string.replace('@@"', '').replace('"@@', '')
