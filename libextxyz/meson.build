# Use 'python' which works cross-platform inside cibuildwheel
python_for_codegen = find_program('python', required: true)

run_command(
    python_for_codegen,
    '..' / 'python' / 'extxyz' / 'extxyz_kv_grammar.py',
    check: true
)

# Build and install the extension module
extxyz_c_sources = ['extxyz.c', 'extxyz_kv_grammar.c']

# Python extension (loaded by cextxyz.py via ctypes.CDLL)
module = python.extension_module(
    '_extxyz',
    extxyz_c_sources,
    install: true,
    subdir: 'extxyz',
    gnu_symbol_visibility: 'default', # keep symbols public on GCC/Clang
    vs_module_defs: '_extxyz.def',    # explicit exports for MSVC (loaded via ctypes)
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