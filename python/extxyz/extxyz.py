"""Compatibility shim — the ASE-aware top-level API was retired in v0.3.0.

Until v0.2.x this module exposed ``read``, ``write``, ``iread`` and
``ExtXYZTrajectoryWriter`` returning / accepting :class:`ase.Atoms`. Those
have moved to the standalone ``ase-extxyz`` package, which registers a
``cextxyz`` format with :mod:`ase.io`. Users should migrate to::

    pip install ase-extxyz
    ase.io.read('file.xyz', format='cextxyz')
    ase.io.write('out.xyz', atoms, format='cextxyz')

The dict/array based core is still exposed at the top level of
:mod:`extxyz` (see :func:`extxyz.iread_dicts` etc.) and has no ASE
dependency.
"""
_MIGRATION_MESSAGE = (
    "extxyz no longer ships an ASE-aware API as of v0.3.0. "
    "Install the `ase-extxyz` plugin and use "
    "`ase.io.read(..., format='cextxyz')` / "
    "`ase.io.write(..., format='cextxyz')` instead. "
    "The dict-based parser is still available as "
    "`extxyz.iread_dicts`, `extxyz.read_dicts`, `extxyz.write_dicts`."
)


def _removed(*_args, **_kwargs):
    raise ImportError(_MIGRATION_MESSAGE)


# Old public names — kept around so that imports fail with a useful message
# instead of an opaque AttributeError.
read = _removed
iread = _removed
write = _removed


class ExtXYZTrajectoryWriter:
    def __init__(self, *_args, **_kwargs):
        raise ImportError(_MIGRATION_MESSAGE)
