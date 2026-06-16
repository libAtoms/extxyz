# Use 'python' which works cross-platform inside cibuildwheel
python_for_codegen = find_program('python', required: true)

run_command(
    python_for_codegen,
    '..' / 'python' / 'extxyz' / 'extxyz_kv_grammar.py',
    check: true
)

# Build and install the extension module
extxyz_c_sources = ['extxyz.c', 'extxyz_kv_grammar.c', 'fast_format.c']

# The _extxyz extension is loaded both via ctypes.CDLL (for write/grammar/stdio)
# and — when built with numpy — imported as a real C-API module for the fast
# read path (pyext.c provides PyInit__extxyz + read_frame). pyext.c is added
# ONLY here, never to the standalone shared library or the C/Fortran drivers.
extxyz_ext_sources = extxyz_c_sources
extxyz_ext_cargs = []
# MSVC exports are pinned by a .def; the numpy build adds PyInit__extxyz so the
# module is importable on Windows, the numpy-less build must NOT list it (the
# symbol doesn't exist then -> link error).
extxyz_ext_def = '_extxyz.def'
if have_numpy
    extxyz_ext_sources += ['pyext.c']
    extxyz_ext_cargs += [numpy_inc_arg]
    extxyz_ext_def = '_extxyz_pyext.def'
endif

# Python extension (loaded by cextxyz.py via ctypes.CDLL, and imported when
# built with the C-API fast read path)
module = python.extension_module(
    '_extxyz',
    extxyz_ext_sources,
    install: true,
    subdir: 'extxyz',
    c_args: extxyz_ext_cargs,
    gnu_symbol_visibility: 'default', # keep symbols public on GCC/Clang
    vs_module_defs: extxyz_ext_def,   # explicit exports for MSVC (loaded via ctypes)
    dependencies: [cleri, pcre2]
)

# Standalone shared library (replaces `make -C libextxyz` from the legacy
# Makefile build path). Same C sources as the Python extension, but plain
# default symbol export — no .def, no Python ABI.
libextxyz = shared_library(
    'extxyz',
    extxyz_c_sources,
    install: true,
    dependencies: [cleri, pcre2],
)

# C-only test driver (replaces `make -C libextxyz cextxyz`).
executable(
    'cextxyz',
    ['test_C_main.c'] + extxyz_c_sources,
    install: false,
    dependencies: [cleri, pcre2],
)

# Exhaustive check that the fast "%16.8f" formatter is byte-identical to printf.
# No pcre2/cleri needed — just the formatter. `meson test` runs a fast subset;
# pass a larger N to the exe for a deeper sweep.
test_fmt_float = executable(
    'test_fmt_float',
    ['test_fmt_float.c', 'fast_format.c'],
    install: false,
    dependencies: cc.find_library('m', required: false),   # ldexp in the test
)
test('fmt_float', test_fmt_float, args: ['1000000'], timeout: 120)

# Fortran demo executable. Requires QUIP's libAtoms; opt in by passing
# -Dquip_lib_dir=... and -Dquip_mod_dir=... to meson setup.
if build_fextxyz
    # libAtoms transitively needs BLAS (openblas) and OpenMP (libgomp under
    # gfortran). Find them via pkg-config first, falling back to plain
    # library search on the host compiler.
    openblas_dep = dependency('openblas', required: false)
    if not openblas_dep.found()
        openblas_dep = cc.find_library('openblas', required: true)
    endif
    fortran = meson.get_compiler('fortran')
    gomp_dep = fortran.find_library('gomp', required: true)

    executable(
        'fextxyz',
        ['test_fortran_main.f90', 'fextxyz.f90'] + extxyz_c_sources,
        install: false,
        fortran_args: ['-I' + quip_mod_dir],
        link_args: ['-L' + quip_lib_dir, '-llibAtoms', '-lf90wrap_stub'],
        build_rpath: quip_lib_dir,
        dependencies: [cleri, pcre2, openblas_dep, gomp_dep],
    )
endif