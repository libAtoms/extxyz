import os
import ctypes
from ctypes.util import find_library

import copy

import numpy as np

class FILE_ptr(ctypes.c_void_p):
    pass

class cleri_grammar_t_ptr(ctypes.c_void_p):
    pass

DATA_I = 1
DATA_F = 2
DATA_B = 3
DATA_S = 4

type_map = {
    DATA_I: ctypes.POINTER(ctypes.c_int),
    DATA_F: ctypes.POINTER(ctypes.c_double),
    DATA_B: ctypes.POINTER(ctypes.c_int),
    DATA_S: ctypes.POINTER(ctypes.c_char_p)
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

# _extxyz.so is actually created as a python extension, but custom builder is
# used to make the name just _extxyz.so, rather than _extxyz.cpython-<vers>-<os>.so
extxyz_so = os.path.join(os.path.abspath(os.path.dirname(__file__)), '_extxyz.so')
extxyz = ctypes.CDLL(extxyz_so)

extxyz.compile_extxyz_kv_grammar.restype = cleri_grammar_t_ptr

extxyz.extxyz_read_ll.args = [ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.POINTER(ctypes.c_int),
                              ctypes.POINTER(Dict_entry_ptr),
                              ctypes.POINTER(Dict_entry_ptr)]

extxyz.extxyz_write_ll.args = [ctypes.c_void_p, ctypes.c_int, Dict_entry_ptr, Dict_entry_ptr]

extxyz.print_dict.args = [Dict_entry_ptr]

extxyz.free_dict.args = [Dict_entry_ptr]

def c_to_py_dict(c_dict, deepcopy=False):
    """
    Convert DictEntry `c_dict` to a Python dict
    """
    result = {}
    node_ptr = c_dict
    while node_ptr:
        node = node_ptr.contents
        data_ptr = ctypes.cast(node.data, type_map[node.data_t])

        if node.nrows == 0 and node.ncols == 0:
            # scalar
            value = data_ptr.contents.value
            # convert to Python primitive types
            if node.data_t == DATA_S:
                value = value.decode('utf-8')
            elif node.data_t == DATA_B:
                value = bool(value)
        else:
            # array, either 1D or 2D
            if node.nrows == 0:
                # vector (1D array)
                if node.data_t == DATA_S:
                    value = np.array([data_ptr[i].decode('utf-8')
                                    for i in range(node.ncols)])
                else:
                    value = np.ctypeslib.as_array(data_ptr, [node.ncols])
            else:
                # matrix (2D array)
                if node.data_t == DATA_S:
                    value = np.array([data_ptr[i].decode('utf-8')
                                      for i in range(node.nrows*node.ncols)])
                    value = value.reshape(node.nrows, node.ncols)
                else:
                    value = np.ctypeslib.as_array(data_ptr,
                                                [node.nrows, node.ncols])
            # convert fake bool integer to python bool
            if node.data_t == DATA_B:
                value = value.astype(bool)

        if deepcopy:
            value = copy.copy(value)

        result[node.key.decode('utf-8')] = value
        node_ptr = node.next
    return result


def py_to_c_dict(py_dict, keys=None):
    """Convert Python dictionary to C DictEntry linked list

    Args:
        py_dict (dict): Input dictionary
        
    Returns:
        c_dict (Dict_entry_ptr): Output linked list
    """
    c_dict = ctypes.cast(ctypes.create_string_buffer(ctypes.sizeof(Dict_entry_struct)), 
                         Dict_entry_ptr)
    node_ptr = c_dict
    
    if keys is None:
        keys = py_dict.keys()
    
    for idx, key in enumerate(keys):
        value = py_dict[key]
        node = node_ptr.contents
        node.key = ctypes.c_char_p(key.encode('utf-8'))
        
        if isinstance(value, list) or isinstance(value, tuple) or isinstance(value, np.ndarray):
            value = np.asarray(value, order='C')  # ensure C-contigous order
            
            if len(value.shape) == 0:
                node.nrows = 0
                node.ncols = 0
            elif len(value.shape) == 1:
                node.nrows = 0
                node.ncols = value.shape[0]
            elif len(value.shape) == 2:
                node.nrows = value.shape[0]
                node.ncols = value.shape[1]
            
            if value.dtype.kind == 'b':
                node.data_t = DATA_B
                value = value.astype(np.int32)
            elif value.dtype.kind == 'i':
                node.data_t = DATA_I
                value = value.astype(np.int32)
            elif value.dtype.kind == 'f':
                node.data_t = DATA_F
                value = value.astype(np.float64)
            elif value.dtype.kind == 's' or value.dtype.kind == 'U':
                node.data_t = DATA_S
                assert len(value.shape) == 1  # only 1D arrays of strings are supported
            else:
                raise TypeError(f"unsupported array dtype {value.dtype}")

            if node.data_t in [DATA_B, DATA_I, DATA_F]:
                nbytes = int(value.dtype.itemsize * np.prod(value.shape))
                buffer = ctypes.create_string_buffer(nbytes)
                ctypes.memmove(buffer, value.ctypes.data, nbytes)
                node.data = ctypes.cast(buffer, ctypes.c_void_p)
            else:
                array_dtype = ctypes.c_char_p * len(value)
                node.data = ctypes.cast(array_dtype(*[str.encode('utf-8') for str in value]),
                                        ctypes.c_void_p)

        elif isinstance(value, str):
            node.data_t = DATA_S
            # NB: data is a char**, not a char*
            node.data = ctypes.cast(ctypes.pointer(ctypes.c_char_p(value.encode('utf-8'))), ctypes.c_void_p)
        elif isinstance(value, bool):
            node.data_t = DATA_B
            node.data = ctypes.cast(ctypes.pointer(ctypes.c_int(value)), ctypes.c_void_p)
        elif isinstance(value, int):
            node.data_t = DATA_I
            node.data = ctypes.cast(ctypes.pointer(ctypes.c_int(value)), ctypes.c_void_p)
        elif isinstance(value, float):
            node.data_t = DATA_F
            node.data = ctypes.cast(ctypes.pointer(ctypes.c_double(value)), ctypes.c_void_p)
        else:
            raise TypeError(f"unsupported type {type(value)}")

        if idx != len(py_dict) - 1:
            # allocate another DictEntry struct unless we're on the last one already
            node.next = ctypes.cast(ctypes.create_string_buffer(ctypes.sizeof(Dict_entry_struct)), 
                                    Dict_entry_ptr)
            node_ptr = node.next

    return c_dict


# construct grammar only once on module initialisation
_kv_grammar = extxyz.compile_extxyz_kv_grammar()

libc_path = find_library('c')
libc = ctypes.CDLL(libc_path)

def cfopen(filename, mode):
    fopen = libc.fopen
    fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    fopen.restype = FILE_ptr
    return fopen(filename.encode('utf-8'),
                 mode.encode('utf-8'))


def cfclose(fp):
    fclose = libc.fclose
    fclose.args = [FILE_ptr]
    fclose(fp)


def read_frame_dicts(fp, verbose=False):
    """Read a single frame using extxyz_read_ll() C function

    Args:
        fp (FILE_ptr): open file pointer, as returned by `cfopen()`
        verbose (bool, optional): Dump C dictionaries to stdout. Defaults to False.

    Returns:
        nat, info, arrays: int, dict, dict
    """
    nat = ctypes.c_int()
    info = Dict_entry_ptr()
    arrays = Dict_entry_ptr()
    eof = False

    try:
        if not extxyz.extxyz_read_ll(_kv_grammar,
                                    fp,
                                    ctypes.byref(nat),
                                    ctypes.byref(info),
                                    ctypes.byref(arrays)):
            eof = True
            raise EOFError()

        if verbose:
            extxyz.print_dict(info)
            extxyz.print_dict(arrays)

        py_info = c_to_py_dict(info, deepcopy=True)
        py_arrays = c_to_py_dict(arrays, deepcopy=True)

    finally:
        if not eof:
            extxyz.free_dict(info)
            extxyz.free_dict(arrays)

    return nat.value, py_info, py_arrays


def write_frame_dicts(fp, nat, info, arrays, columns=None, verbose=False, format_dict=None):
    """Write a single frame using extxyz_write_ll C function

    Args:
        fp (FILE_ptr): open file to which to write
        nat (int): Number of atoms
        info (dict): Python dictionary of per-config data
        arrays (dict): Python dictionary of per-atom data
    """
    nat = ctypes.c_int(nat)
    c_info = py_to_c_dict(info)
    print(c_to_py_dict(c_info))
    
    if columns is None:
        columns = arrays.keys()

    c_arrays = py_to_c_dict(arrays, columns)
    if verbose:
        extxyz.print_dict(c_info)
        extxyz.print_dict(c_arrays)
    if extxyz.extxyz_write_ll(fp, nat, c_info, c_arrays) != 0:
        raise IOError("error writing to extended XYZ file")
