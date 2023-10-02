python3 = find_program('python3')

run_command(
    python3,
    '..' / 'python' / 'extxyz' / 'extxyz_kv_grammar.py'
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