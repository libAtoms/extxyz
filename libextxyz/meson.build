# Use 'python' which works cross-platform inside cibuildwheel
python_for_codegen = find_program('python', required: true)

run_command(
    python_for_codegen,
    '..' / 'python' / 'extxyz' / 'extxyz_kv_grammar.py',
    check: true
)

# Build and install the extension module
# On Windows, add link args to explicitly create the import library
# that meson-python expects but the linker isn't generating
if host_machine.system() == 'windows'
    module = python.extension_module(
        '_extxyz',
        ['extxyz.c', 'extxyz_kv_grammar.c'],
        install: true,
        subdir: 'extxyz',
        gnu_symbol_visibility: 'default',
        dependencies: [cleri, pcre2],
        link_args: ['/EXPORT:PyInit__extxyz']  # Export the init function to force .lib creation
    )
else
    module = python.extension_module(
        '_extxyz',
        ['extxyz.c', 'extxyz_kv_grammar.c'],
        install: true,
        subdir: 'extxyz',
        gnu_symbol_visibility: 'default',
        dependencies: [cleri, pcre2]
    )
endif