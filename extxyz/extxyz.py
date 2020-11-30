import sys
import json
import re
import itertools
from pprint import pprint

import numpy as np

from ase.atoms import Atoms

from pyleri.node import Node
from pyleri import Choice, Regex, Keyword, Token
from extxyz_kv_NB_grammar import (ExtxyzKVGrammar, properties_val_re,
                                  per_atom_column_re, whitespace_re)


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
    
    tf = {'k_true': True,
          'k_false': False}

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

    visit_old_one_d_array = visit_one_d_array    


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
 
   
def result_to_dict(result, verbose=0):
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
    result = {}
    properties = None
    for (key, value) in [node.children for node in tree.children]:
        if isinstance(key.element, Keyword):
            if key.element.name == 'properties':
                if properties is not None:
                    raise KeyError(f'Duplicate properties entry {value.value}')
                properties = value.value
                continue
            else:
                raise KeyError(f'unexpected keyword {key.string}')
        if key.string in result:
            raise KeyError(f'Warning: duplicate key {key.string}')
        result[key.string] = value.value
        
    # look for "Lattice" entry
    try:
        lattice = result.pop('Lattice')
    except KeyError:
        lattice = None
        
    if lattice is not None:
        # convert Lattice to a 3x3 float array
        if lattice.shape == (3,3):
            lattice = lattice.astype(float)
        elif lattice.shape == (3,):
            lattice = np.diag(lattice).astype(float)
        elif lattice.shape == (9,):
            lattice = np.reshape(lattice, (3, 3), order='F').astype(float)
        else:
            raise ValueError(f'Lattice has wrong shape {lattice.shape}')
            
    return result, lattice, properties
    

def read_comment_line(line, verbose=0):
    grammar = ExtxyzKVGrammar()
    result = grammar.parse(line)
    parsed_part = result.tree.children[0].string    
    if not result.is_valid:
        raise SyntaxError(f"Failed to parse entire input line, only '{parsed_part}'. "
                          f'Expecting one of : {result.expecting}')
    return result_to_dict(result, verbose=verbose)


def properties_regex_dtype(properties):   
    regex = ''
    dtype1 = []
    dtype2 = []
    per_atom_dtype = {'R': np.float,
                      'I': np.int,
                      'S': 'U10', # FIXME can we avoid fixed string length?
                      'L': np.bool}
    for (name, property_type, cols) in properties:
        if cols == 1:
            for dtype in (dtype1, dtype2):
                dtype.append((name, per_atom_dtype[property_type]))
        else:
            for col in range(cols):
                regex += per_atom_column_re[property_type] + whitespace_re
                dtype1.append((f'{name}{col}', per_atom_dtype[property_type]))            
            dtype2.append((name, per_atom_dtype[property_type], (cols,)))
    regex = re.compile(regex)
    dtype1 = np.dtype(dtype1)
    dtype2 = np.dtype(dtype2)
    return regex, dtype1, dtype2
    

from io import StringIO

extxyz_to_ase_name_map = {
    'pos': 'positions',
    'species': 'symbols',
    'Z': 'numbers',
    'mass': 'masses'
}

def read_extxyz_frame(file, verbose=0, use_regex=False):
    line = file.readline()
    if not line:
        return None # end of file
    natoms = int(line)
    comment = file.readline()
    info, lattice, properties = read_comment_line(comment, verbose)
    if verbose:
        print('info = ')
        pprint(info)
        print(f'lattice = {repr(lattice)}')
        print(f'properties = {repr(properties)}')
    regex, dtype1, dtype2 = properties_regex_dtype(properties)
    
    if use_regex:
        # not working yet, but something like the following should be possible
        lines = [file.readline() for line in range(natoms)]
        buffer = StringIO(''.join(lines))
        data = np.fromregex(buffer, regex, dtype1)
        data = data.view(dtype2)
    else:
        data = np.genfromtxt(file, dtype2, max_rows=natoms)
        
    data = np.atleast_1d(data) # for 1-atom configs        
    names = list(data.dtype.names)
            
    assert 'pos'in names
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
        # FIXME check for consistency
        symbols = None
    
    atoms = Atoms(symbols=symbols,
                  numbers=numbers,
                  positions=positions,
                  cell=lattice,
                  pbc=lattice is not None)
    
    atoms.info.update(info)
    for name in names:
        ase_name = extxyz_to_ase_name_map.get(name, name)
        atoms.arrays[ase_name] = data[name]
    
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


if __name__ == '__main__':
    configs = read(sys.argv[1], verbose=0)
    print(configs)
    

    
    