import os
import ctypes
import copy

import numpy as np

from ase.atoms import Atoms

class FILE_ptr(ctypes.c_void_p):
    pass

class cleri_grammar_t_ptr(ctypes.c_void_p):
    pass

data_i = 1
data_f = 2
data_b = 3
data_s = 4

type_map = {
    data_i: ctypes.POINTER(ctypes.c_int),
    data_f: ctypes.POINTER(ctypes.c_double),
    data_b: ctypes.POINTER(ctypes.c_int),
    data_s: ctypes.POINTER(ctypes.c_char_p)
}

class Dict_entry_struct(ctypes.Structure):
    pass

Dict_entry_struct._fields_ = [("key", ctypes.c_char_p),
                              ("data", ctypes.c_void_p),                              
                              ("data_t", ctypes.c_int),
                              ("nrows", ctypes.c_int),
                              ("ncols", ctypes.c_int),
                              ("next", ctypes.POINTER(Dict_entry_struct)),
                              ("first_data_ll", ctypes.c_void_p),
                              ("last_data_ll", ctypes.c_void_p),
                              ("n_in_row", ctypes.c_int)]

Dict_entry_ptr = ctypes.POINTER(Dict_entry_struct)

extxyz_so = os.path.join(os.path.abspath(os.path.dirname(__file__)), 
                        'extxyz.so')
extxyz = ctypes.CDLL(extxyz_so)

extxyz.compile_extxyz_kv_grammar.restype = cleri_grammar_t_ptr

extxyz.extxyz_read_ll.args = [ctypes.c_void_p, ctypes.c_void_p, 
                              ctypes.POINTER(ctypes.c_int),
                              ctypes.POINTER(Dict_entry_ptr), 
                              ctypes.POINTER(Dict_entry_ptr)]

extxyz.print_dict.args = [ctypes.POINTER(Dict_entry_ptr)]

extxyz.free_dict.args = [ctypes.POINTER(Dict_entry_ptr)]

def c_to_py_dict(c_dict, deepcopy=False):
    """
    Convert DictEntry `c_dict` as a Python dict
    """
    result = {}
    node_ptr = c_dict
    while node_ptr:
        node = node_ptr.contents
        data_ptr = ctypes.cast(node.data, type_map[node.data_t])
        
        if node.nrows == 0 and node.ncols == 0:
            # scalar
            value = data_ptr.contents.value
            if node.data_t == data_s:
                value = value.decode('utf-8')
        elif node.nrows == 0:
            # vector
            value = np.ctypeslib.as_array(data_ptr, [node.ncols])
        else:
            # matrix
            if node.data_t == data_s:
                value = np.array([data_ptr[i].decode('utf-8') 
                                for i in range(node.nrows)])
            else:            
                value = np.ctypeslib.as_array(data_ptr, 
                                            [node.nrows, node.ncols])
        if deepcopy:
            value = copy.copy(value)
        result[node.key.decode('utf-8')] = value
        node_ptr = node.next
    return result

# construct grammae only once on module initialisation
_kv_grammar = extxyz.compile_extxyz_kv_grammar()

libc = ctypes.CDLL("/usr/lib/libc.dylib")

fopen = libc.fopen
fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
fopen.restype = FILE_ptr

fclose = libc.fclose
fclose.args = [FILE_ptr]

def read_frame(fp):
    try:
        nat = ctypes.c_int()
        info = Dict_entry_ptr()
        arrays = Dict_entry_ptr()

        if not extxyz.extxyz_read_ll(_kv_grammar, 
                                     fp,
                                     ctypes.byref(nat), 
                                     ctypes.byref(info), 
                                     ctypes.byref(arrays)):
            raise IOError('Error within extxyz_read_ll()')
        
        py_info = c_to_py_dict(info, deepcopy=True)
        py_arrays = c_to_py_dict(arrays, deepcopy=True)
        
        cell = py_info.pop('Lattice').reshape((3, 3), order='F').T
        symbols = py_arrays.pop('species')
        positions = py_arrays.pop('pos')
        
        atoms = Atoms(symbols=symbols,
                    positions=positions,
                    cell=cell,
                    pbc=py_info.get('pbc'))
        
        atoms.info.update(py_info)
        atoms.arrays.update(py_arrays)
                        
        assert len(atoms) == nat.value

    finally:
        extxyz.free_dict(info)
        extxyz.free_dict(arrays)
        
    return atoms


def read(filename):
    fp = fopen(filename.encode('utf-8'), 
               "r".encode('utf-8'))
    try:
        atoms = read_frame(fp)
    finally:
        fclose(fp)        
    return atoms
       

if __name__ == '__main__':
    import sys
    atoms = read(sys.argv[1])
    print(atoms)