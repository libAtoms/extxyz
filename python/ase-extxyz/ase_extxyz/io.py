"""ASE plugin: ``cextxyz`` format backed by the libextxyz C parser.

Translates between :class:`extxyz.Frame` (plain dict + numpy) and
:class:`ase.Atoms`.

The single entry point ASE looks up via the ``ase.ioformats`` entry point
is :data:`cextxyz_format`. The ``read_cextxyz`` and ``write_cextxyz``
function names are also discovered automatically by ASE because the
format name is ``cextxyz``.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
from ase.atoms import Atoms
from ase.calculators.calculator import all_properties
from ase.calculators.singlepoint import SinglePointCalculator
from ase.data import atomic_numbers as _ATOMIC_NUMBERS
from ase.units import fs as _ASE_FS
from ase.utils.plugins import ExternalIOFormat

import extxyz
from extxyz import Frame
from extxyz.grammar import Properties

# ----------------------------------------------------------------------------
# ASE plugin registration
# ----------------------------------------------------------------------------

cextxyz_format = ExternalIOFormat(
    desc="Extended XYZ via the libextxyz C parser",
    # '+S' = multi-frame, string filename. We want the path (the C parser
    # opens it through libc); '+F' would have ASE pre-open a Python file
    # handle, which the C parser can't accept.
    code="+S",
    module="ase_extxyz.io",
    # ``ext`` intentionally not set — the ``extxyz`` built-in already claims
    # ``.xyz``; users opt in via format='cextxyz'.
)


# ----------------------------------------------------------------------------
# Frame ↔ Atoms translation
# ----------------------------------------------------------------------------

# Per-atom array name mapping; second tuple slot is an optional converter
# that takes (atoms, value) and returns the ASE-side value.
_EXTXYZ_TO_ASE = {
    'pos':     ('positions', None),
    'species': ('symbols',   None),
    'Z':       ('numbers',   None),
    'mass':    ('masses',    None),
    'velo':    ('momenta',   lambda atoms, v: (v / _ASE_FS) * atoms.get_masses()[:, None]),
}

_ASE_TO_EXTXYZ = {
    'positions': ('pos',     None),
    'symbols':   ('species', None),
    'numbers':   ('Z',       None),
    'masses':    ('mass',    None),
    'momenta':   ('velo',    lambda atoms, p: p / atoms.get_masses()[:, None] * _ASE_FS),
}


def _species_to_numbers(species: np.ndarray) -> np.ndarray:
    """Vectorized symbol-string → atomic-number lookup.

    ``ase.symbols.symbols2numbers`` does the dict lookup once per atom; for
    typical frames with K << N unique species we can do K lookups and a
    single ``np.take``, which is much cheaper at large N.
    """
    unique_syms, inverse = np.unique(species, return_inverse=True)
    unique_nums = np.fromiter(
        (_ATOMIC_NUMBERS[s] for s in unique_syms),
        dtype=int, count=len(unique_syms),
    )
    return unique_nums[inverse]


def _frame_to_atoms(frame: Frame, *,
                    create_calc: bool = False,
                    calc_prefix: str = '') -> Atoms:
    """Build an :class:`ase.Atoms` from one :class:`extxyz.Frame`.

    The frame's numpy buffers (positions and any per-atom extras) are
    aliased into ``atoms.arrays`` rather than copied. This skips ASE's
    ``new_array`` per-array ``np.array(..., order='C')`` copy, which is
    the dominant cost for large frames.
    """
    arrays_in = frame.arrays  # don't copy unless we mutate

    try:
        positions = arrays_in['pos']
    except KeyError:
        raise ValueError("frame has no 'pos' column")

    species = arrays_in.get('species')
    numbers = arrays_in.get('Z')
    if numbers is None:
        if species is None:
            raise ValueError("frame has neither 'species' nor 'Z' column")
        numbers = _species_to_numbers(species)
    elif species is not None:
        if np.any(_species_to_numbers(species) != numbers):
            raise ValueError(f'inconsistent symbols {species} and numbers {numbers}')

    cell = frame.cell.T if frame.cell.any() else None

    # Construct without positions: ASE allocates a throwaway zeros((N, 3))
    # which we immediately overwrite with the parser's buffer (no memcpy).
    atoms = Atoms(numbers=numbers, cell=cell, pbc=frame.pbc)
    atoms.arrays['positions'] = positions

    # Per-atom extras — direct assign to skip new_array's copy.
    for name, value in arrays_in.items():
        if name in ('pos', 'species', 'Z'):
            continue
        mapping = _EXTXYZ_TO_ASE.get(name)
        if mapping is None:
            out_name = name
        else:
            out_name, converter = mapping
            if converter is not None:
                value = converter(atoms, value)
        atoms.arrays[out_name] = value

    if create_calc:
        info = dict(frame.info)
        # Pass a shallow dict copy so the calc creator doesn't pop calc-related
        # keys out of atoms.arrays — preserves the old behaviour where forces
        # etc. are visible in both atoms.arrays and atoms.calc.results.
        atoms.calc = _create_single_point_calculator(
            atoms, info, dict(atoms.arrays), calc_prefix)
        atoms.info.update(info)
    elif frame.info:
        atoms.info.update(frame.info)
    return atoms


def _atoms_to_frame(atoms: Atoms, *,
                    columns=None,
                    write_calc: bool = False,
                    calc_prefix: str = '',
                    verbose: int = 0) -> Frame:
    """Build a :class:`extxyz.Frame` from one :class:`ase.Atoms`."""
    if write_calc and atoms.calc is not None:
        # capture calc before copy() — Atoms.copy() doesn't copy the calculator
        original_calc = atoms.calc
        atoms = atoms.copy()
        _update_atoms_from_calc(atoms, original_calc, calc_prefix)

    info = dict(atoms.info)
    arrays_in = dict(atoms.arrays)

    arrays_in, columns = _ensure_species_pos(atoms, arrays_in, columns)

    out_arrays: dict[str, np.ndarray] = {}
    for column in columns:
        value = arrays_in[column]
        try:
            Properties.format_map[value.dtype.kind]
        except KeyError:
            if verbose:
                print(f'skipping "{column}" unsupported dtype.kind {value.dtype.kind}')
            continue
        ext_name, converter = _ASE_TO_EXTXYZ.get(column, (column, None))
        if converter is not None:
            value = converter(atoms, value)
        out_arrays[ext_name] = value

    cell = np.asarray(atoms.cell.array, dtype=float)
    pbc = np.asarray(atoms.get_pbc(), dtype=bool)
    return Frame(natoms=len(atoms), cell=cell, pbc=pbc, info=info, arrays=out_arrays)


def _ensure_species_pos(atoms, arrays, columns):
    """Reorder so 'symbols' and 'positions' come first."""
    skip_keys = ['symbols', 'positions', 'numbers']
    if columns is None:
        columns = (['symbols', 'positions']
                   + [k for k in arrays.keys() if k not in skip_keys])
    else:
        columns = list(columns)

    def shuffle(column, idx):
        if column not in columns:
            raise ValueError(f'invalid XYZ structure: missing "{column}"')
        old = columns.index(column)
        columns[idx], columns[old] = columns[old], columns[idx]

    shuffle('symbols', 0)
    shuffle('positions', 1)

    new_arrays = {}
    for column in columns:
        if column == 'symbols':
            new_arrays[column] = np.array(atoms.get_chemical_symbols())
        else:
            new_arrays[column] = arrays[column]
    return new_arrays, columns


# ----------------------------------------------------------------------------
# Calculator <-> info/arrays glue (lifted from extxyz.utils, ASE-aware)
# ----------------------------------------------------------------------------

_PER_ATOM_PROPERTIES = ['forces', 'stresses', 'charges', 'magmoms', 'energies']
_PER_CONFIG_PROPERTIES = ['energy', 'stress', 'dipole', 'magmom', 'free_energy']


def _create_single_point_calculator(atoms, info=None, arrays=None, calc_prefix=''):
    """Move ``calc_prefix*`` keys out of info/arrays and into a SinglePointCalculator."""
    if info is None:
        info = atoms.info
    if arrays is None:
        arrays = atoms.arrays
    results = {}
    for prop in all_properties:
        key = calc_prefix + prop
        if prop in _PER_CONFIG_PROPERTIES and key in info:
            results[prop] = info.pop(key)
        elif prop in _PER_ATOM_PROPERTIES and key in arrays:
            results[prop] = arrays.pop(key)
    if 'virial' in info:
        try:
            from ase.constraints import full_3x3_to_voigt_6_stress
        except ImportError:
            from ase.stress import full_3x3_to_voigt_6_stress
        virial = info.pop('virial')
        results['stress'] = -full_3x3_to_voigt_6_stress(virial / atoms.get_volume())
    if 'virials' in arrays:
        try:
            from ase.constraints import full_3x3_to_voigt_6_stress
        except ImportError:
            from ase.stress import full_3x3_to_voigt_6_stress
        virials = arrays.pop('virials')
        results['stresses'] = -full_3x3_to_voigt_6_stress(virials / atoms.get_volume())
    if not results:
        return None
    return SinglePointCalculator(atoms, **results)


def _update_atoms_from_calc(atoms, calc=None, calc_prefix=''):
    """Move calculator results back into info/arrays for serialization."""
    if calc is None:
        calc = atoms.calc
    if calc is None:
        return
    for prop, value in calc.results.items():
        key = calc_prefix + prop
        if prop in _PER_CONFIG_PROPERTIES:
            atoms.info[key] = value
        elif prop in _PER_ATOM_PROPERTIES:
            atoms.arrays[key] = value


# ----------------------------------------------------------------------------
# ASE entry points: read_cextxyz / write_cextxyz
# ----------------------------------------------------------------------------

def _normalize_index(index):
    """Translate ASE's index argument into something iread_dicts can take.

    Returns ``(forward_slice_or_none, post_slice)`` where:
    - ``forward_slice_or_none`` is what to pass to ``iread_dicts(index=...)``
      (so we read lazily when possible). ``None`` means read everything.
    - ``post_slice`` is applied to the resulting list of frames in memory,
      e.g. for negative indices.
    """
    if isinstance(index, str):
        from ase.io.formats import string2index
        index = string2index(index)
    if index is None:
        return slice(None), None
    if isinstance(index, int):
        if index >= 0:
            return slice(index, index + 1), None
        # Negative single index: read all, slice in memory.
        return None, index
    if isinstance(index, slice):
        has_neg = ((index.start is not None and index.start < 0) or
                   (index.stop is not None and index.stop < 0))
        if has_neg:
            return None, index
        return index, None
    raise TypeError(f'unsupported index {index!r}')


def read_cextxyz(filename, index=-1, *,
                 use_cextxyz: bool = True,
                 use_regex: bool = False,
                 create_calc: bool = False,
                 calc_prefix: str = '',
                 verbose: int = 0):
    """Yield :class:`ase.Atoms` from an extxyz file.

    Generator that yields one ``Atoms`` per frame, sliced by ``index``.
    ``filename`` is a path-like — ASE passes the path through to us
    because the format's IOFormat code is ``+S`` (see :data:`cextxyz_format`).
    """
    forward, post = _normalize_index(index)

    if forward is not None:
        for frame in extxyz.iread_dicts(filename, index=forward,
                                        use_cextxyz=use_cextxyz,
                                        use_regex=use_regex,
                                        verbose=verbose):
            yield _frame_to_atoms(frame, create_calc=create_calc,
                                  calc_prefix=calc_prefix)
        return

    # Negative indexing: buffer all frames, then apply the slice.
    frames = list(extxyz.iread_dicts(filename,
                                     use_cextxyz=use_cextxyz,
                                     use_regex=use_regex,
                                     verbose=verbose))
    if isinstance(post, int):
        yield _frame_to_atoms(frames[post], create_calc=create_calc,
                              calc_prefix=calc_prefix)
    else:
        for frame in frames[post]:
            yield _frame_to_atoms(frame, create_calc=create_calc,
                                  calc_prefix=calc_prefix)


def write_cextxyz(filename, images, *,
                  use_cextxyz: bool = True,
                  append: bool = False,
                  columns=None,
                  write_calc: bool = False,
                  calc_prefix: str = '',
                  format_dict=None,
                  verbose: int = 0):
    """Write one or many :class:`ase.Atoms` as extxyz frames.

    ``filename`` is a path; the C writer opens it via libc. (For streaming
    output during an ASE optimizer / MD run, attach a callable that calls
    ``ase.io.write(filename, atoms, format='cextxyz', append=True)`` per step
    — that pattern reopens the file each call but still uses the C writer.)
    """
    if isinstance(images, Atoms):
        images = [images]

    def gen():
        for atoms in images:
            yield _atoms_to_frame(atoms, columns=columns,
                                  write_calc=write_calc,
                                  calc_prefix=calc_prefix,
                                  verbose=verbose)

    extxyz.write_dicts(filename, gen(),
                       use_cextxyz=use_cextxyz,
                       append=append,
                       columns=columns,
                       format_dict=format_dict,
                       verbose=verbose)


# ----------------------------------------------------------------------------
# Streaming writer — keeps one libc FILE* open across many .write() calls
# ----------------------------------------------------------------------------

class ExtXYZTrajectoryWriter:
    """Stateful writer that opens the file once and keeps the libc FILE*
    alive across calls. Use this when attaching to an ASE optimizer or
    dynamics, where ``ase.io.write(..., format='cextxyz', append=True)`` per
    step would re-open the file every iteration.

        >>> from ase.optimize import LBFGS
        >>> with ExtXYZTrajectoryWriter('opt.xyz', atoms=atoms) as traj:
        ...     opt = LBFGS(atoms)
        ...     opt.attach(traj, interval=1)
        ...     opt.run(fmax=1e-3)

    The writer goes through the C writer (``cextxyz.write_frame_dicts``)
    directly, never re-opening the file.
    """

    def __init__(self, filename, mode='w', atoms=None,
                 columns=None, write_calc: bool = False,
                 calc_prefix: str = ''):
        from extxyz import cextxyz
        self._cextxyz = cextxyz
        self._fp = cextxyz.cfopen(str(filename), mode)
        self.atoms = atoms
        self.columns = columns
        self.write_calc = write_calc
        self.calc_prefix = calc_prefix

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def __call__(self, atoms=None):
        # ASE optimizer.attach() calls the trajectory directly.
        self.write(atoms)

    def write(self, atoms=None, *, verbose: int = 0):
        if atoms is None:
            atoms = self.atoms
        if atoms is None:
            raise ValueError("ExtXYZTrajectoryWriter.write() needs atoms")
        frame = _atoms_to_frame(atoms,
                                columns=self.columns,
                                write_calc=self.write_calc,
                                calc_prefix=self.calc_prefix,
                                verbose=verbose)
        # Order: ensure species + pos come first in the column list.
        cols = list(frame.arrays.keys())
        for special in ('pos', 'species'):
            if special in cols:
                cols.remove(special)
        if 'species' in frame.arrays:
            cols.insert(0, 'species')
        if 'pos' in frame.arrays:
            cols.insert(1 if 'species' in frame.arrays else 0, 'pos')

        info = dict(frame.info)
        info['Lattice'] = frame.cell.T
        info['pbc'] = frame.pbc

        self._cextxyz.write_frame_dicts(self._fp, frame.natoms, info,
                                        {k: frame.arrays[k] for k in cols},
                                        cols, verbose)

    def close(self):
        if self._fp is not None:
            self._cextxyz.cfclose(self._fp)
            self._fp = None
