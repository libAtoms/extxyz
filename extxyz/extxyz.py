import sys
import json
import re
import os
import argparse

from pprint import pprint
from io import StringIO

import numpy as np
from numpy.core.arrayprint import (get_printoptions,
                                   _get_format_function)

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
tw = 0.0

def read_comment_line(line, verbose=0):
    """
    Use pyleri to parse an extxyz comment line
    """
    global tg, td

    t0 = time.time()
    result = grammar.parse(line)
    tg += time.time() - t0
    parsed_part = result.tree.children[0].string
    if not result.is_valid:
        raise SyntaxError(f"Failed to parse entire input line, only '{parsed_part}'. "
                          f'Expecting one of : {result.expecting}')
    t0 = time.time()
    d = result_to_dict(result, verbose=verbose)
    td += time.time() - t0
    return d


def properties_to_dtype(properties):
    """
    Determine numpy dtypes from list of property definitions
    """
    dtype_scalar = []
    dtype_vector = []
    per_atom_dtype = {'R': np.float,
                      'I': np.int,
                      'S': 'U10', # FIXME can we avoid fixed string length?
                      'L': np.bool}
    for (name, property_type, cols) in properties:
        if cols == 1:
            for dtype in (dtype_scalar, dtype_vector):
                dtype.append((name, per_atom_dtype[property_type]))                
        else:
            for col in range(cols):
                dtype_scalar.append((f'{name}{col}', per_atom_dtype[property_type]))
            dtype_vector.append((name, per_atom_dtype[property_type], (cols,)))
    dtype_scalar = np.dtype(dtype_scalar)
    dtype_vector = np.dtype(dtype_vector)
    return dtype_scalar, dtype_vector

def properties_to_regex(properties):
    regex = ''
    for (name, property_type, cols) in properties:
        this_regex = '('+per_atom_column_re[property_type]+')' + whitespace_re
        if cols == 1:
            regex += this_regex
        else:
            for col in range(cols):
                regex += this_regex
    regex = re.compile(regex)
    return regex


def properties_to_property_str(properties):
    property_strs = []
    for (name, property_type, cols) in properties:
        property_strs.append(f'{name}:{property_type}:{cols}')
    return ':'.join(property_strs)


_canonical_property_values = {
    'R': np.array(0.0),
    'I': np.array(0),
    'S': np.array('str'),
    'L': np.array(True)
}

def properties_to_format_strings(properties, format_dict):
    def make_func(v):
        return lambda x: v
    formatter = { k: make_func(v) for k, v in format_dict['per-config'].items()}
    options = get_printoptions()
    options['formatter'] = formatter
    
    format_strings = []
    for (_, property_type, ncols) in properties:
        value = _canonical_property_values[property_type]
        format_func = _get_format_function(value, 
                                           **options)
        format_string = format_func(value.item)
        format_strings.extend([format_string for col in range(ncols)])
    return format_strings

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

# map from extxyz name to ASE name, and optionally conversion function
extxyz_to_ase_name_map = {
    'pos': ('positions', None),
    'species': ('symbols', None),
    'Z': ('numbers', None),
    'mass': ('masses', None), # FIXME should we convert QUIP mass units to amu?
    'velo': ('momenta', velo_to_momenta)
}

# inverse mapping - not automatically generated due to conversion functions
ase_to_extxyz_name_map = {
    'positions': ('pos', None),
    'symbols': ('species', None),
    'numbers': ('Z', None),
    'masses': ('mass', None), # FIXME should we convert amu to QUIP mass units?
    'momenta': ('velo', velo_to_momenta)
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
    dtype_scalar, dtype_vector = properties_to_dtype(properties)

    if use_regex:
        lines = [next(file) for line in range(natoms)]
        buffer = StringIO(''.join(lines))
        data = np.fromregex(buffer, regex, dtype_scalar)
        data = data.view(dtype_vector)
    else:
        data = np.genfromtxt(file, dtype_vector, max_rows=natoms)
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
                  pbc=lattice is not None) # FIXME or should we check for pbc in info?

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


def atoms_to_structured_array(atoms, arrays, columns=None, verbose=0):
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

    skip_keys = ['symbols', 'positions', 'numbers']
    if columns is None:
        columns = (['symbols', 'positions'] + 
                   [key for key in arrays.keys() if key not in skip_keys])
    else:
        columns = columns[:] # make a copy so we can reorder
        
    shuffle_columns('symbols', 0)
    shuffle_columns('positions', 1)
    
    values = []
    properties = []
    for column in columns:
        if column == 'symbols':
            value = np.array(atoms.get_chemical_symbols())
        else:
            value = arrays[column]
        try:
            property_type = format_map[value.dtype.kind]
        except KeyError:
            if verbose:
                print('skipping "{column}" unsupported dtype.kind {dtype.kind}')
            continue
        values.append(value)
        property_name, _ = ase_to_extxyz_name_map.get(column, (column, None))
        if (len(value.shape) == 1
                or (len(value.shape) == 2 and value.shape[1] == 1)):
            ncols = 1
        else:
            ncols = value.shape[1]
        properties.append((property_name, property_type, ncols))            

    _, dtype_vector = properties_to_dtype(properties)
    data = np.zeros(len(atoms), dtype_vector)
    for (name, _, _), value in zip(properties, values):
        data[name] = value
    return data, properties


default_extxyz_format_dict = {
    'per-config': {
        'float':    '%.8f',
        'int':      '%d',
        'object':   '%s',
        'numpystr': '%s',
        'bool':     '%.1s'
    },
    'per-atom': {
        'float':    '%16.8f',
        'int':      '%8d',
        'object':   '%s',
        'numpystr': '%s',
        'bool':     '%.1s'
    }
}

def escape(string):
    if '"' in string or ' ' in string:
        string = string.replace('"', r'\"')
        string = f'"{string}"'
    return string


def extxyz_value_to_string(value, formatter):
    if isinstance(value, str):
        return escape(value)
    value = np.asarray(value)
    string = np.array2string(value,
                             separator=',',
                             max_line_width=np.inf,
                             threshold=np.inf,
                             formatter=formatter)
    string = string.replace('\n', '')
    return string


def extxyz_dict_to_str(info, format_dict):
    def make_func(v):
        return lambda x: v % x
    formatter = {k: make_func(v) for k, v in format_dict['per-config'].items()}
    
    output = ''
    for key, value in info.items():
        key = escape(key)
        value = extxyz_value_to_string(value, formatter)
        output += f'{key}={value} '    
    return output.strip()


def write_extxyz_frame(file, atoms, info=None, arrays=None, columns=None,
                       write_calc=False, calc_prefix='', verbose=0,
                       format_dict=None):
    if format_dict is None:
        format_dict = default_extxyz_format_dict
    if write_calc:
        tmp_atoms = atoms.copy()
        update_atoms_from_calc(tmp_atoms, atoms.calc, calc_prefix)
        atoms = tmp_atoms
    if info is None:
        info = atoms.info
    if arrays is None:
        arrays = atoms.arrays

    data, properties = atoms_to_structured_array(atoms, 
                                                 arrays,
                                                 columns,
                                                 verbose=verbose)

    file.write(f'{len(atoms)}\n')
    info_dict = info.copy()
    info_dict['Lattice'] = atoms.cell.array.T
    info_dict['pbc'] = atoms.get_pbc() # FIXME should this always be included? Reader doesn't parse it
    info_dict['Properties'] = properties_to_property_str(properties)
    comment = extxyz_dict_to_str(info_dict, format_dict)
    
    file.write(comment + '\n')
    dtype_scalar, _ = properties_to_dtype(properties)
    data_columns = data.view(dtype_scalar)
    format_strings = properties_to_format_strings(properties, format_dict) 
    np.savetxt(file, data_columns, fmt=format_strings)


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


class ExtxyzTrajectoryWriter:
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
        >>> traj = ExtxyzTrajectoryWriter('out.xyz')
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+')
    parser.add_argument('-v', '--verbose', action='count',  default=0)
    parser.add_argument('-r', '--regex', action='store_true')
    parser.add_argument('-c', '--create-calc', action='store_true')
    parser.add_argument('-p', '--calc-prefix', action='store', default='')
    parser.add_argument('-w', '--write', action='store_true')
    parser.add_argument('-R', '--round-trip', action='store_true')
    args = parser.parse_args()
    if args.round_trip:
        args.write = True # -R implies -w too

    configs = {}
    for file in args.files:
        print(f'Reading from {file}')
        configs[file] = read(file,
                             verbose=args.verbose,
                             use_regex=args.regex,
                             create_calc=args.create_calc,
                             calc_prefix=args.calc_prefix)
        if args.verbose:
            print(file)
            config = configs[file]
            if isinstance(config, Atoms):
                config = [config]
            for atoms in config:
                pprint(atoms.info)
                

    print('TIMER grammar.parse', tg, 'result_to_dict', td)    
            
    if args.write:
        t0 = time.time()
        out_files = []
        for file in args.files:
            out_file = os.path.splitext(file)[0] + '.out.xyz'
            out_files.append(out_file)
            write(out_file, configs[file], 
                verbose=args.verbose,
                write_calc=args.create_calc,
                calc_prefix=args.calc_prefix)
        tw = time.time() - t0
        print('TIMER write', tw)
        
    if args.round_trip:
        new_configs = {}
        for out_file in out_files:
            print(f'Re-reading from {out_file}')
            new_configs[file] = read(out_file,
                                     verbose=args.verbose,
                                     use_regex=args.regex,
                                     create_calc=args.create_calc,
                                     calc_prefix=args.calc_prefix)
            
        for config, new_config in zip(configs.values(), 
                                      new_configs.values()):
            assert config == new_config
        
