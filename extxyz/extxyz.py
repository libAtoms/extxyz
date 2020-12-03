import sys
import json
import re
import os
import argparse

from pprint import pprint
from io import StringIO

import numpy as np

import ase.units as units
from ase.atoms import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from ase.constraints import full_3x3_to_voigt_6_stress
from ase.symbols import symbols2numbers

from pyleri.node import Node
from pyleri import Choice, Regex, Keyword, Token
from extxyz_kv_NB_grammar import (ExtxyzKVGrammar, properties_val_re,
                                  per_atom_column_re, whitespace_re)

import time ##

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

    def __init__(self):
        self.depth = 0

    def generic_visit(self, node):
        if isinstance(node, Node):
            name = getattr(node.element, 'name', None)
            str_repr = (f'{node.element.__class__.__name__}'
                       f'(name={name}, string="{node.string}")')
        else:
            str_repr = str(node)

        print('  ' * self.depth + str_repr)
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
        name = getattr(node.element, 'name', None)
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

    tf = {'k_true':  True,
          'k_false': False}

    def visit_properties(self, node):
        return Value(node.element.name)

    def visit_r_barestring(self, node):
        return Value(node.string)

    def visit_r_quotedstring(self, node):
        return Value(node.string[1:-1])

    def visit_r_float(self, node):
        return Value(float(node.string))

    def visit_r_integer(self, node):
        return Value(int(node.string))

    def visit_k_true(self, node):
        return Value(ExtractValues.tf[node.element.name])

    visit_k_false = visit_k_true

    def visit_strings(self, node):
        return Value([c.string for c in node.children])

    def visit_ints(self, node):
        return Value([int(c.string) for c in node.children])

    visit_ints_sp = visit_ints

    def visit_floats(self, node):
        return Value([float(c.string) for c in node.children])

    visit_floats_sp = visit_floats

    def visit_bools(self, node):
        return Value([ExtractValues.tf[c.element.name] for c in node.children])

    visit_bools_sp = visit_bools

    def visit_properties_val_str(self, node):
        items = node.string.split(':')
        items = [ items[3 * i:3 * i + 3] for i in range(len(items) // 3)]
        result = [ (prop[0], prop[1], int(prop[2])) for prop in items ]
        return Value(result)


class OneDimArrays(NodeTransformer):
    """
    Convert one-dimensional arrays to numpy arrays
    """
    def visit_one_d_array(self, node):
        assert len(node.children) == 1
        return Value(np.array(node.children[0].value))

    def visit_old_one_d_array(self, node):
        result = self.visit_one_d_array(node)
        if result.value.shape == (9, ):
            result.value = result.value.reshape((3, 3), order='F')
        return result


class OneDimToTwoDim(NodeTransformer):
    """
    Combine one dimensional arrays to form two dimensional arrays
    """
    def visit_one_d_arrays(self, node):
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
        else:
            raise ValueError(f'Lattice has wrong shape {lattice.shape}')
    return lattice


def result_to_dict(result, verbose=0):
    """
    Convert from pyleri parse result to key/value info dictionary
    """
    tree = result.tree.children[0]
    if verbose >= 1:
        print('input tree:')
        TreeDumper().visit(tree)
    tree = TreeCleaner().visit(tree)
    tree = ExtractValues().visit(tree)
    if verbose >= 2:
        print('cleaned tree:')
        TreeDumper().visit(tree)
    tree = OneDimArrays().visit(tree)
    tree = OneDimToTwoDim().visit(tree)
    tree = TwoDimArrays().visit(tree)
    if verbose >=1 :
        print('final tree:')
        TreeDumper().visit(tree)

    # now we should have a flat list of (key, value) pairs
    result_dict = {}
    properties = None
    for (key, value) in [node.children for node in tree.children]:
        if key.value == 'properties':
            if properties is not None:
                raise KeyError(f'Duplicate properties entry {value.value}')
            properties = value.value
            continue
        if key.value in result_dict:
            raise KeyError(f'duplicate key {key.value}')
        if not isinstance(value, Value):
            raise ValueError(f'unsupported value {value}')
        result_dict[key.value] = value.value

    lattice = extract_lattice(result_dict)

    return result_dict, lattice, properties

tg = 0.0
td = 0.0

def read_comment_line(line, verbose=0):
    """
    Use pyleri to parse an extxyz comment line
    """
    global tg, td

    t0 = time.time()
    result = grammar.parse(line)
    tg += time.time()-t0
    parsed_part = result.tree.children[0].string
    if not result.is_valid:
        raise SyntaxError(f"Failed to parse entire input line, only '{parsed_part}'. "
                          f'Expecting one of : {result.expecting}')
    t0 = time.time()
    d = result_to_dict(result, verbose=verbose)
    td += time.time()-t0
    return d


def properties_regex_dtype(properties):
    """
    Determine a regex and numpy dtype from parsed property definition
    """
    regex = ''
    dtype1 = []
    dtype2 = []
    per_atom_dtype = {'R': np.float,
                      'I': np.int,
                      'S': 'U10', # FIXME can we avoid fixed string length?
                      'L': np.bool}
    for (name, property_type, cols) in properties:
        this_regex = '('+per_atom_column_re[property_type]+')' + whitespace_re
        if cols == 1:
            regex += this_regex
            for dtype in (dtype1, dtype2):
                dtype.append((name, per_atom_dtype[property_type]))
        else:
            for col in range(cols):
                regex += this_regex
                dtype1.append((f'{name}{col}', per_atom_dtype[property_type]))
            dtype2.append((name, per_atom_dtype[property_type], (cols,)))
    regex = re.compile(regex)
    dtype1 = np.dtype(dtype1)
    dtype2 = np.dtype(dtype2)
    return regex, dtype1, dtype2


def velo_to_momenta(atoms, velo):
    masses = atoms.get_masses()
    return (velo / units.fs) * masses[:, None]


extxyz_to_ase_name_map = {
    'pos': ('positions', None),
    'species': ('symbols', None),
    'Z': ('numbers', None),
    'mass': ('masses', None),
    'velo': ('momenta', velo_to_momenta)
}

# partition ase.calculators.calculator.all_properties into two lists:
#  'per-atom' and 'per-config'
per_atom_properties = ['forces',  'stresses', 'charges',  'magmoms', 'energies']
per_config_properties = ['energy', 'stress', 'dipole', 'magmom', 'free_energy']

def create_single_point_calculator(atoms, info=None, arrays=None, calc_prefix=''):
    """
    Move results from info/arrays dicts to an attached SinglePointCalculator

    Args:
        atoms (ase.Atoms): input structure
        info (dict, optional): Dictionary of per-config values. Defaults to atoms.info
        arrays (dict, optional): Dictionary of per-atom values. Defaults to atoms.arrays
        calc_prefix (str, optional): String prefix to prepend to canonical name
    """
    if info is None:
        info = atoms.info
    if arrays is None:
        arrays = atoms.arrays
    calc_results = {}

    # first check for per-config properties, energy, free_energy etc.
    for prop in per_config_properties:
        if calc_prefix + prop in info:
            calc_results[prop] = info.pop(calc_prefix + prop)

    # special case for virial -> stress conversion
    if calc_prefix + 'virial' in info:
        virial = info.pop(calc_prefix + 'virial')
        stress = - full_3x3_to_voigt_6_stress(virial / atoms.get_volume())
        if 'stress' in calc_results:
            raise RuntimeError(f'stress {stress} and virial {virial} both present')
        calc_results['stress'] = stress

    # now the per-atom properties - forces, energies, etc.
    for prop in per_atom_properties:
        if calc_prefix + prop in arrays:
            calc_results[prop] = arrays.pop(calc_prefix + prop)

    # special case for local_virial -> stresses conversion
    if calc_prefix + 'local_virial' in arrays:
        virials = arrays.pop(calc_prefix + 'local_virial')
        stresses = - full_3x3_to_voigt_6_stress(virials / atoms.get_volume())
        if 'stresses' in calc_results:
            raise RuntimeError(f'stresses {stresses} and virial {virials} both present')
        calc_results['stress'] = stress

    calc = None
    if calc_results:
        calc = SinglePointCalculator(atoms, **calc_results)
    return calc


def read_extxyz_frame(file, verbose=0, use_regex=True,
                      create_calc=False, calc_prefix=''):
    """
    Read a single frame in extxyz format from `file`.
    """
    file = iter(file)
    try:
        line = next(file)
    except StopIteration:
        return None # end of file
    natoms = int(line)
    comment = next(file)
    info, lattice, properties = read_comment_line(comment, verbose)
    if verbose:
        print('info = ')
        pprint(info)
        print(f'lattice = {repr(lattice)}')
        print(f'properties = {repr(properties)}')
    regex, dtype1, dtype2 = properties_regex_dtype(properties)

    if use_regex:
        lines = [next(file) for line in range(natoms)]
        buffer = StringIO(''.join(lines))
        data = np.fromregex(buffer, regex, dtype1)
        data = data.view(dtype2)
    else:
        data = np.genfromtxt(file, dtype2, max_rows=natoms)
    data = np.atleast_1d(data) # for 1-atom configs

    names = list(data.dtype.names)
    assert 'pos' in names
    positions = data['pos']
    names.remove('pos')

    symbols = None
    if 'species' in names:
        symbols = data['species']
        names.remove('species')

    numbers = None
    if 'Z' in names:
        numbers = data['Z']
        names.remove('Z')
    if symbols is not None and numbers is not None:
        if np.any(symbols2numbers(symbols) != numbers):
            raise ValueError(f'inconsistent symbols {symbols} '
                             f'and numbers {numbers}')
        symbols = None

    atoms = Atoms(symbols=symbols,
                  numbers=numbers,
                  positions=positions,
                  cell=lattice,
                  pbc=lattice is not None)

    # convert per-atoms data to ASE expectations
    arrays = {}
    for name in names:
        ase_name, converter = extxyz_to_ase_name_map.get(name, (name, None))
        value = data[name]
        if converter is not None:
            value = converter(atoms, value)
        arrays[ase_name] = value

    # optionally create a SinglePointCalculator from stored results
    if create_calc:
        atoms.calc = create_single_point_calculator(atoms, info, arrays)

    atoms.info.update(info)
    atoms.arrays.update(arrays)
    return atoms


def iread(file, **kwargs):
    own_fh = False
    if isinstance(file, str):
        if file == '-':
            file = sys.stdin
        else:
            file = open(file, 'r')
            own_fh = True
    try:
        while file:
            atoms = read_extxyz_frame(file, **kwargs)
            if atoms is None:
                break
            yield atoms
    finally:
        if own_fh: file.close()


def read(file, **kwargs):
    configs = list(iread(file, **kwargs))
    if len(configs) == 1:
        return configs[0]
    else:
        return configs


def update_atoms_from_calc(atoms, calc=None, calc_prefix=''):
    if calc is None:
        calc = atoms.calc
    for prop, value in calc.results.items():
        if prop in per_config_properties:
            atoms.info[calc_prefix + prop] = value
        elif prop in per_atom_properties:
            atoms.arrays[calc_prefix + prop] = value
        else:
            raise KeyError(f'unknown property {prop}')


def format_properties(arrays, columns=None):
    # map from numpy dtype.kind to extxyz property type
    format_map = {'d': 'R',
                  'f': 'R',
                  'i': 'I',
                  'O': 'S',
                  'S': 'S',
                  'U': 'S'}

    def shuffle_columns(column, idx):
        if column in columns:
            old_idx = columns.index(column)
            columns[idx], columns[old_idx] = columns[idx], columns[old_idx]
        else:
            raise ValueError(f'invalid XYZ file: does not contain "{column}"')

    skip_keys = ['symbols', 'properties', 'numbers']        
    if columns is None:
        columns = (['symbols', 'positions'] + 
                   [key for key in arrays.keys() if key not in skip_keys])
    else:
        columns = columns[:] # make a copy so we can reorder
        
    shuffle_columns('symbols', 0)
    shuffle_columns('positions', 1)
    
    dtype = []
    result = ''
    for column in columns:
        value = arrays[column]
        property_type = format_map[value.dtype.kind]
        ncols = np.atleast_2d(value).shape[1]
        dtype.append((column, value.dtype, ncols))        
        result += f'{column}:{property_type}:{ncols}'
        
    # build a structured array from the per-atom data
    data = np.array([arrays[column] for column in columns], dtype)        
    return result, data


default_extyz_formatter = {
    'bool': lambda x: 'T' if x else 'F'
}

def extxyz_value_to_string(value, formatter=None, suppress_newline=True):
    if formatter is None:
        formatter = default_extyz_formatter    
    value = np.asarray(value)
    string = np.array2string(value,
                             separator=',',
                             max_line_width=np.inf,
                             threshold=np.inf,
                             formatter=formatter)
    if suppress_newline:
        string = string.replace('\n', '')
    return string


def escape(string):
    if (' ' in string or
            '"' in string or "'" in string or
            '{' in string or '}' in string or
            '[' in string or ']' in string):
        string = string.replace('"', r'\"')
        string = f'"{string}"'
    return string


def extxyz_dict_to_str(info, formatter=None):
    output = ''
    for key, value in info.items():
        key = escape(key)
        value = extxyz_value_to_string(value, formatter)
        value = escape(value)
        output += f'{key}={value} '    
    return output.strip()


def write_extxyz_frame(file, atoms, info=None, arrays=None,
                       write_calc=False, calc_prefix='', verbose=0,
                       formatter=None):
    if write_calc:
        tmp_atoms = atoms.copy()
        update_atoms_from_calc(tmp_atoms, atoms.calc, calc_prefix)
        atoms = tmp_atoms
    if info is None:
        info = atoms.info
    if arrays is None:
        arrays = atoms.arrays

    file.write(f'{len(atoms)}\n')
        
    info_dict = info.copy()
    info_dict['Lattice'] = atoms.cell.array.T
    info_dict['pbc'] = atoms.get_pbc()
    info_dict['Properties'], data = format_properties(arrays, columns)
    comment = extxyz_dict_to_str(info_dict, formatter)
        
    file.write(comment + '\n')
    file.write(extxyz_value_to_string(data, formatter))


def write(file, atoms, **kwargs):
    own_fh = False
    if isinstance(file, str):
        if file == '-':
            file = sys.stdout
        else:
            file = open(file, 'w')
            own_fh = True
    try:
        configs = atoms
        if not isinstance(configs, list):
            configs = [atoms]
        for atoms in configs:
            write_extxyz_frame(file, atoms, **kwargs)
    finally:
        if own_fh: file.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+')
    parser.add_argument('-v', '--verbose', action='count',  default=0)
    parser.add_argument('-r', '--regex', action='store_true')
    parser.add_argument('-c', '--create-calc', action='store_true')
    parser.add_argument('-p', '--calc-prefix', action='store', default='')
    args = parser.parse_args()

    configs = {}
    for file in args.files:
        print(f'Reading from {file}')
        configs[file] = read(file,
                             verbose=args.verbose,
                             use_regex=args.regex,
                             create_calc=args.create_calc,
                             calc_prefix=args.calc_prefix)
        if args.verbose:
            print(configs[file])

    print('grammar.parse', tg, 'result_to_dict', td)            
            
    for file in args.file:
        output_file = os.path.splitext(file)[0] + '.out.xyz'
        print(f'Writing to {output_file}')
        write(output_file, configs[file], 
              verbose=args.verbose,
              write_calc=args.create_calc,
              calc_prefix=args.calc_prefix)





>>>>>>> e72f4c56e472ef4becc9c2c47b04759dde74c079
