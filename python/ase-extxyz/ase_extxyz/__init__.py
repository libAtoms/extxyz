"""ASE I/O plugin backed by the libextxyz C parser.

Importing this package has no side effects; ASE discovers the
``cextxyz`` format through the ``ase.ioformats`` entry point declared in
``pyproject.toml`` and lazily imports :mod:`ase_extxyz.io` when the format
is first used.
"""
__version__ = "0.1.1"
