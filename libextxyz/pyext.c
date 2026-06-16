/* CPython C-API entry point for the fast read path.
 *
 * This translation unit is compiled ONLY into the `_extxyz` Python extension
 * module (see libextxyz/meson.build) — never into the standalone libextxyz
 * shared library or the C/Fortran test drivers, which must stay free of any
 * Python/numpy dependency. It calls the unchanged C core (extxyz_read_ll_opts)
 * and marshals the resulting DictEntry linked lists straight into Python
 * dicts of numpy arrays / scalars, replacing the former per-node ctypes loop
 * in cextxyz.py (c_to_py_dict).
 *
 * The marshalling here must stay byte-for-byte equivalent to c_to_py_dict;
 * benchmarks/verify_marshal.py checks new-vs-legacy output on real data.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <cleri/cleri.h>
#include "extxyz.h"

/* Module-level exception, mirrors cextxyz.ExtXYZError. */
static PyObject *ExtXYZError = NULL;

/* Build the Python value for one DictEntry node. Returns a new reference, or
 * NULL with a Python exception set. Mirrors c_to_py_dict() exactly. */
static PyObject *node_to_value(DictEntry *node)
{
    const enum data_type t = node->data_t;
    const int nrows = node->nrows;
    const int ncols = node->ncols;

    /* ---- scalar ---- */
    if (nrows == 0 && ncols == 0) {
        switch (t) {
        case data_i:
            return PyLong_FromLong(*(int *)node->data);
        case data_f:
            return PyFloat_FromDouble(*(double *)node->data);
        case data_b:
            return PyBool_FromLong(*(int *)node->data);
        case data_s:
            return PyUnicode_FromString(*(char **)node->data);
        default:
            PyErr_Format(ExtXYZError, "unsupported scalar data type %d", (int)t);
            return NULL;
        }
    }

    /* ---- array (vector or matrix) ---- */
    const int is_matrix = (nrows > 0);
    npy_intp dims[2];
    int ndim;
    npy_intp n;
    if (is_matrix) {
        ndim = 2;
        dims[0] = nrows;
        dims[1] = ncols;
        n = (npy_intp)nrows * (npy_intp)ncols;
    } else {
        ndim = 1;
        dims[0] = ncols;
        n = ncols;
    }

    if (t == data_i || t == data_f || t == data_b) {
        /* dtypes chosen to match the legacy np.ctypeslib.as_array output:
         * int -> int32, double -> float64, bool -> (int32 then astype bool). */
        if (t == data_f) {
            PyObject *arr = PyArray_SimpleNew(ndim, dims, NPY_FLOAT64);
            if (!arr) return NULL;
            memcpy(PyArray_DATA((PyArrayObject *)arr), node->data,
                   (size_t)n * sizeof(double));
            return arr;
        }
        if (t == data_i) {
            PyObject *arr = PyArray_SimpleNew(ndim, dims, NPY_INT32);
            if (!arr) return NULL;
            memcpy(PyArray_DATA((PyArrayObject *)arr), node->data,
                   (size_t)n * sizeof(int32_t));
            return arr;
        }
        /* data_b: C stores int (0/1); legacy produced a NPY_BOOL array. */
        PyObject *arr = PyArray_SimpleNew(ndim, dims, NPY_BOOL);
        if (!arr) return NULL;
        const int *src = (const int *)node->data;
        npy_bool *dst = (npy_bool *)PyArray_DATA((PyArrayObject *)arr);
        for (npy_intp i = 0; i < n; i++)
            dst[i] = src[i] ? 1 : 0;
        return arr;
    }

    if (t == data_s) {
        if (node->n_in_row < 0) {
            /* contiguous fixed-width buffer: width = -n_in_row bytes/cell.
             * Mirror _read_contiguous_strings: frombuffer('S{w}').astype(str)
             * => fixed-width NPY_UNICODE ('U{w}'), trailing nulls dropped. */
            const int width = -node->n_in_row;
            npy_intp uni_dims[2];
            for (int d = 0; d < ndim; d++) uni_dims[d] = dims[d];
            PyObject *arr = PyArray_New(&PyArray_Type, ndim, uni_dims,
                                        NPY_UNICODE, NULL, NULL,
                                        width * 4 /* UCS4 itemsize */, 0, NULL);
            if (!arr) return NULL;
            const unsigned char *base = (const unsigned char *)node->data;
            char *out = (char *)PyArray_DATA((PyArrayObject *)arr);
            memset(out, 0, (size_t)n * (size_t)width * 4);
            for (npy_intp i = 0; i < n; i++) {
                const unsigned char *cell = base + (size_t)i * (size_t)width;
                Py_UCS4 *d = (Py_UCS4 *)(out + (size_t)i * (size_t)width * 4);
                for (int c = 0; c < width; c++) {
                    if (cell[c] == 0) break;
                    d[c] = (Py_UCS4)cell[c];
                }
            }
            return arr;
        }
        /* scattered char**: decode each into a Python list, let numpy infer the
         * 'U{maxlen}' dtype exactly as np.array([...]) did. Rare, not hot. */
        PyObject *list = PyList_New(n);
        if (!list) return NULL;
        char **src = (char **)node->data;
        for (npy_intp i = 0; i < n; i++) {
            PyObject *s = PyUnicode_FromString(src[i]);
            if (!s) { Py_DECREF(list); return NULL; }
            PyList_SET_ITEM(list, i, s); /* steals ref */
        }
        PyObject *flat = PyArray_FromAny(list, NULL, 0, 0,
                                         NPY_ARRAY_DEFAULT, NULL);
        Py_DECREF(list);
        if (!flat) return NULL;
        if (is_matrix) {
            PyArray_Dims shape = { dims, ndim };
            PyObject *reshaped = PyArray_Newshape((PyArrayObject *)flat, &shape,
                                                  NPY_CORDER);
            Py_DECREF(flat);
            return reshaped;
        }
        return flat;
    }

    PyErr_Format(ExtXYZError, "unsupported data type %d", (int)t);
    return NULL;
}

/* Convert a DictEntry linked list to a new Python dict, or NULL on error. */
static PyObject *dict_to_py(DictEntry *head)
{
    PyObject *result = PyDict_New();
    if (!result) return NULL;
    for (DictEntry *node = head; node; node = node->next) {
        PyObject *value = node_to_value(node);
        if (!value) { Py_DECREF(result); return NULL; }
        if (PyDict_SetItemString(result, node->key, value) != 0) {
            Py_DECREF(value);
            Py_DECREF(result);
            return NULL;
        }
        Py_DECREF(value);
    }
    return result;
}

/* read_frame(grammar_addr:int, fp_addr:int, use_tokenizer:int,
 *            comment:str|None=None, use_cleri:int=1)
 *            -> (nat:int, info:dict, arrays:dict)
 * Raises EOFError at end of file, ExtXYZError on a parse error. */
static PyObject *py_read_frame(PyObject *self, PyObject *args)
{
    (void)self;
    unsigned long long grammar_addr, fp_addr;
    int use_tokenizer;
    const char *comment = NULL;
    int use_cleri = 1;
    if (!PyArg_ParseTuple(args, "KKi|zi", &grammar_addr, &fp_addr,
                          &use_tokenizer, &comment, &use_cleri))
        return NULL;

    cleri_grammar_t *grammar = (cleri_grammar_t *)(uintptr_t)grammar_addr;
    FILE *fp = (FILE *)(uintptr_t)fp_addr;

    int nat = 0;
    DictEntry *info = NULL, *arrays = NULL;
    char error_message[1024];
    error_message[0] = '\0';

    int ok;
    Py_BEGIN_ALLOW_THREADS
    ok = extxyz_read_ll_opts(grammar, fp, &nat, &info, &arrays,
                             (char *)comment, error_message, use_tokenizer,
                             use_cleri);
    Py_END_ALLOW_THREADS

    if (!ok) {
        /* Mirror the EOF heuristic in cextxyz.read_frame_dicts. */
        if (error_message[0] == '\0' ||
            strncmp(error_message,
                    "Failed to parse int natoms from ' ", 34) == 0) {
            PyErr_SetNone(PyExc_EOFError);
        } else {
            /* Raw message; the Python wrapper normalises it (.strip().replace)
             * to stay byte-identical with the legacy ctypes path. */
            PyErr_SetString(ExtXYZError, error_message);
        }
        /* info/arrays are not owned by us on failure (see cextxyz.py). */
        return NULL;
    }

    PyObject *py_info = dict_to_py(info);
    PyObject *py_arrays = py_info ? dict_to_py(arrays) : NULL;

    free_dict(info);
    free_dict(arrays);

    if (!py_info || !py_arrays) {
        Py_XDECREF(py_info);
        Py_XDECREF(py_arrays);
        return NULL;
    }
    return Py_BuildValue("(iNN)", nat, py_info, py_arrays);
}

static PyMethodDef extxyz_methods[] = {
    {"read_frame", py_read_frame, METH_VARARGS,
     "read_frame(grammar_addr, fp_addr, use_tokenizer, comment=None) -> "
     "(nat, info, arrays). Reads and marshals one frame in C."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef extxyz_module = {
    PyModuleDef_HEAD_INIT, "_extxyz",
    "C-API fast read path for extxyz (additive to the ctypes interface).",
    -1, extxyz_methods, NULL, NULL, NULL, NULL,
};

PyMODINIT_FUNC PyInit__extxyz(void)
{
    import_array();
    PyObject *m = PyModule_Create(&extxyz_module);
    if (!m) return NULL;
    ExtXYZError = PyErr_NewException("_extxyz.ExtXYZError", NULL, NULL);
    if (!ExtXYZError) { Py_DECREF(m); return NULL; }
    Py_INCREF(ExtXYZError);
    if (PyModule_AddObject(m, "ExtXYZError", ExtXYZError) != 0) {
        Py_DECREF(ExtXYZError);
        Py_DECREF(m);
        return NULL;
    }
    return m;
}
