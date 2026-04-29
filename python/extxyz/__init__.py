"""extxyz — fast Extended XYZ parser/writer (no ASE dependency).

The dict-based public API:

* :class:`Frame`            — one parsed frame
* :func:`iread_dicts`       — yield Frame instances
* :func:`read_dicts`        — eager, returns Frame or list[Frame]
* :func:`write_dicts`       — write one or many Frame

To use extxyz with ASE, install the ``ase-extxyz`` plugin package which
registers a ``cextxyz`` format with :mod:`ase.io`.
"""
from ._version import __version__
from .core import Frame, iread_dicts, read_dicts, write_dicts

__all__ = [
    '__version__',
    'Frame',
    'iread_dicts',
    'read_dicts',
    'write_dicts',
]
