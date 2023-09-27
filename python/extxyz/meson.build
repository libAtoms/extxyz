conf_data = configuration_data()
conf_data.set('VERSION', meson.project_version())
version_file = configure_file(
    input: '_version.py.in',
    output: '_version.py',
    configuration: conf_data
)

# Pure Python sources
python_sources = [
    '__init__.py',
    '__main__.py',
    version_file,
    'cli.py',
    'extxyz.py',
    'cextxyz.py',
    'extxyz_kv_grammar.py',
    'utils.py'
]

# Install pure Python
python.install_sources(
    python_sources,
    subdir: 'extxyz'
)