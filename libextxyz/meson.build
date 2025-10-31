# Use 'python' which works cross-platform inside cibuildwheel
python_for_codegen = find_program('python', required: true)

run_command(
    python_for_codegen,
    '..' / 'python' / 'extxyz' / 'extxyz_kv_grammar.py',
    check: true
)

# Build and install the extension module
module = python.extension_module(
    '_extxyz', # Name of the module
    ['extxyz.c', 'extxyz_kv_grammar.c'], 
    install: true,  # Install it
    subdir: 'extxyz',
    gnu_symbol_visibility: 'default', # keep symbols public
    dependencies: [cleri, pcre2]
)