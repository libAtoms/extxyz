import sys
import json
import re

from pathlib import PosixPath

from itertools import islice, count
from pprint import pprint
from io import StringIO

import numpy as np
from numpy.core.arrayprint import (get_printoptions,
                                   _get_format_function)

import ase.units as units
from ase.utils import lazyproperty
from ase.atoms import Atoms
from ase.symbols import symbols2numbers

from pyleri.node import Node
from .extxyz_kv_grammar import (ExtxyzKVGrammar,
                                float_re, integer_re, bool_re, simplestring_re,
                                whitespace_re, integer_fmt, float_fmt, string_fmt, bool_fmt)
from . import cextxyz
from .utils import create_single_point_calculator, update_atoms_from_calc

import time

grammar = ExtxyzKVGrammar()

class NodeVisitor:
    """
    Implementation of the Visitor pattern for a pyleri parse tree. Walks the
    tree calling a visitor function for every node found. The visitor methods
    should be defined in subclasses as ``visit_`` plus either (1) the name, or
    (2) the qclass name of the element, e.g. ``visit_floats` or `visit_Regex`.
    If no visitor function is found the `generic_visit` visitor is used instead.
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
    """
    Subclass of `Visitor` which allows tree to be modified.
    Walks the parse tree and uses the return value of the
    visitor methods to replace or remove old nodes. If the return
    value of the visitor method is ``None``, the node will be removed.
    """

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
    """
    Subclass of `NodeVisitor` which prints a textual representation
    of the parse tree.
    """

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
        """
        Remove all tokens
        """
        return None

    def visit_Choice(self, node):
        """
        Collapse Choice nodes, since these contain only a single child node
        """
        child = node.children[0]
        if getattr(child.element, 'name', None) is None:
            child.element.name = node.element.name
        return self.visit(child)

    def visit_Regex(self, node):
        """
        Remove unnamed Regex nodes
        """
        if not hasattr(node.element, 'name'):
            return None
        return self.generic_visit(node)

class Value:
    def __init__(self, value):
        """
        Node to represent a parsed value
        """
        self.value = value

    def __repr__(self):
        return f'Value({repr(self.value)})'


class ExtractValues(NodeTransformer):
    """
    Convert scalars and list of floats ints, strings, bools to Python types
    """

    tf = {'r_true':  True,
          'r_false': False}

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
    """
    Convert one-dimensional arrays to numpy arrays
    """
    def visit_one_d_array(self, node):
        assert len(node.children) == 1
        return Value(np.array(node.children[0].value))

    visit_one_d_array_i = visit_one_d_array
    visit_one_d_array_f = visit_one_d_array
    visit_one_d_array_b = visit_one_d_array
    visit_one_d_array_s = visit_one_d_array

    def visit_old_one_d_array(self, node):
        result = self.visit_one_d_array(node)
        if result.value.shape == (9, ):
            result.value = result.value.reshape((3, 3), order='F')
        elif result.value.shape == (1, ):
            # old array with one column is just a scalar
            result.value = result.value.item()
        return result


class OneDimToTwoDim(NodeTransformer):
    """
    Combine one dimensional arrays to form two dimensional arrays
    """
    def visit_one_d_arrays(self, node):
        row_types = [c.value.dtype for c in node.children]
        # if (any([t != np.int64 and t != np.float64 for t in row_types]) and
            # not all([t != row_types[0] for t in row_types])):
            # raise ValueError(f'Got 2-D array with mismatching row types {row_types}')
        return Value(np.array([c.value for c in node.children]))


class TwoDimArrays(NodeTransformer):
    def visit_two_d_array(self, node):
        assert len(node.children) == 1
        return Value(node.children[0].value)


def extract_lattice(result_dict):
    """
    extract "Lattice" entry and apply semantic conversions
    """
    try:
        lattice = result_dict.pop('Lattice')
    except KeyError:
        lattice = None
    if lattice is not None:
        # convert Lattice to a 3x3 float array
        if lattice.shape == (3, 3):
            lattice = lattice.astype(float)
        elif lattice.shape == (3,):
            lattice = np.diag(lattice).astype(float)
        elif lattice.shape == (9,):
            lattice = np.reshape(lattice, (3, 3), order='F').astype(float)
        else:
            raise ValueError(f'Lattice has wrong shape {lattice.shape}')
    return lattice


def velo_to_momenta(atoms, velo):
    """
    input: velocities in A/fs
    output: momenta in amu * A / (ASE time unit)
    """
    masses = atoms.get_masses()
    return (velo / units.fs) * masses[:, None]


def momenta_to_velo(atoms, momenta):
    """
    input: momenta in amu * A / (ASE time unit)
    output: velocities in A/fs
    """
    masses = atoms.get_masses()
    return momenta / masses[:, None] * units.fs


def ensure_species_pos(atoms, arrays, columns=None):
    """
    Ensure species and position occur in first two columns
    """
    def shuffle_columns(column, idx):
        if column in columns:
            old_idx = columns.index(column)
            columns[idx], columns[old_idx] = columns[idx], columns[old_idx]
        else:
            raise ValueError(f'invalid XYZ structure: does not contain "{column}"')

    if arrays is None:
        arrays = atoms.arrays
    skip_keys = ['symbols', 'positions', 'numbers']
    if columns is None:
        columns = (['symbols', 'positions'] +
                [key for key in arrays.keys() if key not in skip_keys])
    else:
        columns = columns[:] # make a copy so we can reorder

    shuffle_columns('symbols', 0)
    shuffle_columns('positions', 1)

    new_arrays = {}
    for column in columns:        
        if column == 'symbols':
            new_arrays[column] = np.array(atoms.get_chemical_symbols())
        else:
            new_arrays[column] = arrays[column]

    return new_arrays, columns

class Properties:
    per_atom_dtype = {'R': float,
                      'I': int,
                      'S': 'U10', # FIXME can we avoid fixed string length?
                      'L': bool}
    
    # map from numpy dtype.kind to extxyz property type
    format_map = {'d': 'R',
                  'f': 'R',
                  'i': 'I',
                  'O': 'S',
                  'S': 'S',
                  'U': 'S'}
        
    # map from extxyz name to ASE name, and optionally conversion function
    extxyz_to_ase = {
        'pos': ('positions', None),
        'species': ('symbols', None),
        'Z': ('numbers', None),
        'mass': ('masses', None), # FIXME should we convert QUIP mass units to amu?
        'velo': ('momenta', velo_to_momenta)
    }

    # inverse mapping - not automatically generated due to conversion functions
    ase_to_extxyz = {
        'positions': ('pos', None),
        'symbols': ('species', None),
        'numbers': ('Z', None),
        'masses': ('mass', None), # FIXME should we convert amu to QUIP mass units?
        'momenta': ('velo', momenta_to_velo)
    }
    
    # regular expressions for data columns, imported from grammar definition
    per_atom_column_re = {
        'R': float_re,
        'I': integer_re,
        'S': simplestring_re,
        'L': bool_re
    }
    
    default_format_dict = {
        'R': float_fmt,
        'I': integer_fmt,
        'S': string_fmt,
        'L': bool_fmt
    }

    def __init__(self, property_string=None, properties=None, format_dict=None, data=None):
        if (property_string is None) + (properties is None) != 1:
            raise ValueError('exactly one of property_string and properties '
                             f'should be present; got {property_string} and '
                             f'{properties} respectively.')

        if property_string:
            items = property_string.split(':')
            items = [ items[3 * i:3 * i + 3] for i in range(len(items) // 3)]
            self.properties = [ (prop[0], prop[1], int(prop[2])) for prop in items ]
        else:
            self.properties = properties
            
        if format_dict is None:
            format_dict = Properties.default_format_dict
        self.format_dict = format_dict
        self._data = data
                    
    def __iter__(self):
        for (name, _, _) in self.properties:
            yield name
            
    @classmethod
    def from_atoms(cls, atoms, arrays, columns=None, verbose=0,
                   format_dict=None):
        arrays, columns = ensure_species_pos(atoms, arrays, columns)
        values = []
        properties = []
        for column in columns:
            value = arrays[column]
            try:
                property_type = Properties.format_map[value.dtype.kind]
            except KeyError:
                if verbose:
                    print('skipping "{column}" unsupported dtype.kind {dtype.kind}')
                continue
            values.append(value)
            property_name, _ = Properties.ase_to_extxyz.get(column, (column, None))
            if (len(value.shape) == 1
                    or (len(value.shape) == 2 and value.shape[1] == 1)):
                ncols = 1
            else:
                ncols = value.shape[1]
            properties.append((property_name, property_type, ncols))

        self = cls(properties=properties, format_dict=format_dict)
        self._data = np.zeros(len(atoms), self.dtype_vector)
        for name, value in zip(self, values):
            self._data[name] = value
        return self
    
    def get_arrays(self, atoms, names=None, ase_names=True):
        arrays = {}
        if names is None:
            names = self
        for name in names:
            converter = None
            if ase_names:
                out_name, converter = Properties.extxyz_to_ase.get(name, (name, None))
            else:
                out_name = name
            value = self.data[name]
            if converter is not None:
                value = converter(atoms, value)
            arrays[out_name] = value
        return arrays

    def get_dtype(self, scalar=True):
        """
        Construct numpy dtypes from property definitions
        """
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
        if scalar:
            return np.dtype(dtype_scalar)
        else:
            return np.dtype(dtype_vector)

    @lazyproperty
    def dtype_scalar(self):
        return self.get_dtype(scalar=True)

    @lazyproperty
    def dtype_vector(self):
        return self.get_dtype(scalar=False)

    @lazyproperty
    def regex(self):
        regex = r'^\s*'
        for (_, property_type, cols) in self.properties:
            this_regex = '('+Properties.per_atom_column_re[property_type]+')' + whitespace_re
            for col in range(cols):
                regex += this_regex
        regex = re.sub('.' * len(whitespace_re) + '$', '', regex)
        regex = re.compile(regex, flags=re.M)
        return regex

    @lazyproperty
    def property_string(self):
        property_strs = []
        for (name, property_type, cols) in self.properties:
            property_strs.append(f'{name}:{property_type}:{cols}')
        return ':'.join(property_strs)

    @lazyproperty
    def format_strings(self):
        format_strings = []
        for (_, property_type, ncols) in self.properties:
            format_string = self.format_dict[property_type]
            format_strings.extend([format_string for col in range(ncols)])
        return format_strings
    
    @property
    def data(self):
        return self._data
    
    @data.setter
    def data(self, data):
        self._data = np.atleast_1d(data.view(self.dtype_vector))
    
    @property
    def data_columns(self):
        return self._data.view(self.dtype_scalar)


def result_to_dict(result, verbose=0):
    """
    Convert from pyleri parse result to key/value info dictionary
    """
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
    if verbose >=1 :
        print('final tree:')
        TreeDumper('final').visit(tree)

    # now we should have a flat list of (key, value) pairs
    result_dict = {}
    for (key, value) in [node.children for node in tree.children]:
        if key.value in result_dict:
            raise KeyError(f'duplicate key {key.value}')
        if not isinstance(value, Value):
            raise ValueError(f'unsupported value {value}, key {key.value}')
        result_dict[key.value] = value.value

    return result_dict


def read_comment_line(line, verbose=0):
    """
    Use pyleri to parse an extxyz comment line
    """
    result = grammar.parse(line)
    parsed_part = result.tree.children[0].string
    if not result.is_valid:
        raise SyntaxError(f"Failed to parse entire input line, only '{parsed_part}'. "
                          f'Expecting one of : {result.expecting}')
    return result_to_dict(result, verbose=verbose)


def read_frame_dicts(file, verbose=0, use_regex=True):
    file = iter(file)
    try:
        line = next(file)
    except StopIteration:
        raise EOFError()
    if re.match(r'^\s*$', line):
        # blank line assume end of file
        raise EOFError()

    natoms = int(line)
    comment = next(file)
    info = read_comment_line(comment, verbose)
    if len(info) == 0:
        info['comment'] = comment.strip()
    if verbose:
        print('read_frame info = ')
        print("info")
        pprint(info)
        
    properties = info.pop('properties', 'species:S:1:pos:R:3')
    properties = Properties(property_string=properties)

    if use_regex:
        lines = [next(file) for line in range(natoms)]
        buffer = StringIO(''.join(lines))
        data = np.fromregex(buffer, properties.regex, properties.dtype_scalar)
    else:
        data = np.genfromtxt(file, properties.dtype_vector, max_rows=natoms)
        
    return natoms, info, data, properties   


def read_frame(file, verbose=0, use_cextxyz=True,
               use_regex=True, create_calc=False, calc_prefix=''):
    """
    Read a single frame in extxyz format from `file`.
    """

    try:
        if use_cextxyz:
            natoms, info, arrays = cextxyz.read_frame_dicts(file, verbose=verbose)        
            properties = info.pop('Properties', 'species:S:1:pos:R:3')
            properties = Properties(property_string=properties)
            data = np.zeros(natoms, properties.dtype_vector)
            for name, value in arrays.items():
                data[name] = value            
        else:
            natoms, info, data, properties = read_frame_dicts(file, verbose=verbose, 
                                                                use_regex=use_regex)
    except EOFError:
        return None
    
    properties.data = data
    lattice = extract_lattice(info)

    names = list(properties.dtype_vector.names)
    assert 'pos' in names
    positions = properties.data['pos']
    names.remove('pos')

    symbols = None
    if 'species' in names:
        symbols = properties.data['species']
        names.remove('species')

    numbers = None
    if 'Z' in names:
        numbers = properties.data['Z']
        names.remove('Z')
    if symbols is not None and numbers is not None:
        if np.any(symbols2numbers(symbols) != numbers):
            raise ValueError(f'inconsistent symbols {symbols} '
                             f'and numbers {numbers}')
        symbols = None

    if 'pbc' in info:
        pbc = info['pbc']
        del info['pbc']
    else:
        pbc = [True]*3

    atoms = Atoms(symbols=symbols,
                  numbers=numbers,
                  positions=positions,
                  cell=lattice.T if lattice is not None else None,
                  pbc=pbc)

    # work with a copy of arrays so we can remove results if necessary
    arrays = properties.get_arrays(atoms, names)

    # optionally create a SinglePointCalculator from stored results
    if create_calc:
        atoms.calc = create_single_point_calculator(atoms, info, arrays, calc_prefix)

    atoms.info.update(info)
    atoms.arrays.update(arrays)
    return atoms


def iread(file, index=None, use_cextxyz=True, **kwargs):
    own_fh = False
    if isinstance(file, str) or isinstance(file, PosixPath):
        if use_cextxyz:
            file = cextxyz.cfopen(str(file), 'r')
            own_fh = True
        else:
            if file == '-':
                file = sys.stdin
            else:
                file = open(file, 'r')
                own_fh = True
    elif index is not None:
        raise ValueError('`index` argument cannot be used with open files')

    if index is None or index == ':':
        index = slice(None, None, None)

    if not isinstance(index, (slice, str)):
        index = slice(index, (index + 1) or None)

    if (index.start is not None and index.start < 0) or (index.stop is not None and index.stop < 0):
        raise ValueError("Negative indices not (yet) supported in extxyz.iread()")

    current_frame = 0
    frames = islice(count(0), index.start, index.stop, index.step)
    try:
        for frame in frames:
            while current_frame <= frame:
                atoms = read_frame(file, use_cextxyz=use_cextxyz, **kwargs)
                current_frame += 1
                if atoms is None:
                    break
            if atoms is None:
                break
            yield atoms
    finally:
        if own_fh:
            if use_cextxyz:
                cextxyz.cfclose(file)
            else:
                file.close()


def read(file, **kwargs):
    configs = list(iread(file, **kwargs))
    if len(configs) == 1:
        return configs[0]
    else:
        return configs


def escape(string):
    have_special = (' ' in string or '=' in string or '"' in string or ',' in string or '[' in string or
                    ']' in string or '{' in string or '}' in string or '\\' in string or '\n' in string)
    out_string = ''
    for c in string:
        if c == '\n':
            out_string += '\\n';
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
        # elif isinstance(obj, np.int32) or isinstance(obj, np.int64):
        #     return int(obj)
        # elif isinstance(obj, np.float32) or isinstance(obj, np.float64):
        #     return float(obj)
        elif isinstance(obj, bool):
            return _tf(obj)
        return super().default(obj)


def extxyz_value_to_string(value):
    if isinstance(value, str):
        return escape(value)
    else:
        string = ExtXYZEncoder().encode(value)
        return string.replace('@@"', '').replace('"@@', '')

"""
Write `atoms` to `file` in extended XYZ format.
"""
def write(file, atoms, use_cextxyz=True, append=False, columns=None,
          write_calc=False, calc_prefix='', verbose=0, format_dict=None):
    own_fh = False
    mode = 'w'
    if append: mode = 'a'
    if use_cextxyz:
        file = cextxyz.cfopen(str(file), mode)
        own_fh = True
    else:        
        if isinstance(file, str):
            if file == '-':
                file = sys.stdout
            else:
                file = open(file, mode)
                own_fh = True
    try:
        configs = atoms
        if not isinstance(configs, list):
            configs = [atoms]
        for atoms in configs:
            if write_calc:
                tmp_atoms = atoms.copy()
                update_atoms_from_calc(tmp_atoms, atoms.calc, calc_prefix)
                atoms = tmp_atoms
            info = atoms.info.copy()
            arrays = atoms.arrays.copy()

            info['Lattice'] = atoms.cell.array.T
            info['pbc'] = atoms.get_pbc()
            properties = Properties.from_atoms(atoms, arrays,
                                               columns, verbose=verbose,
                                               format_dict=format_dict)

            if use_cextxyz:
                if format_dict is not None:
                    raise ValueError('C extxyz writer does not (yet) support custom format strings')
                cextxyz.write_frame_dicts(file, 
                                          len(atoms), 
                                          info, 
                                          properties.get_arrays(atoms, ase_names=False),
                                          columns,
                                          verbose)
            else:
                file.write(f'{len(atoms)}\n')
                info['Properties'] = properties.property_string
                comment =  ' '.join([f'{escape(k)}={extxyz_value_to_string(v)}' for k, v in info.items()])
                file.write(comment + '\n')
                np.savetxt(file, properties.data_columns, fmt=properties.format_strings)

    finally:
        if own_fh:
            if use_cextxyz:
                cextxyz.cfclose(file)
            else:            
                file.close()


class ExtXYZTrajectoryWriter:
    def __init__(self, filename, mode='w', atoms=None, **kwargs):
        """
        Convenience wrapper for writing trajectories in extended XYZ format

        Can be attached to ASE dynamics, optimizers, etc:

        >>> from extxyz import ExtxyzTrajectoryWriter
        >>> from ase.calculators.emt import EMT
        >>> from ase.optimizers import LBFGS
        >>> from ase.build imprort bulk
        >>> atoms = bulk('Cu') * (3, 3, 3)
        >>> atoms.calc = EMT()
        >>> atoms.rattle(0.1)
        >>> traj = ExtxyzTrajectoryWriter('out.xyz', atoms=atoms)
        >>> opt = LBFGS(atoms, trajectory=traj) # or opt.attach(traj)
        >>> opt.run(fmax=1e-3)
        """
        self.file = open(filename, mode)
        self.atoms = atoms
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def close(self):
        self.file.close()

    def write(self, atoms=None, **kwargs):
        if atoms is None:
            atoms = self.atoms
        all_kwargs = self.kwargs.copy()
        all_kwargs.update(kwargs)
        write(self.file, atoms, **all_kwargs)

