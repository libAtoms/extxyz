"""ASE-free dict/array based extxyz read & write API.

Public surface:

* :class:`Frame` — a dataclass holding one parsed frame.
* :func:`iread_dicts` — yields :class:`Frame` instances.
* :func:`read_dicts` — eager wrapper around :func:`iread_dicts`.
* :func:`write_dicts` — writes a list/iterator of :class:`Frame` instances.

The :mod:`ase_extxyz.io` plugin module wraps these to translate
:class:`Frame` ↔ :class:`ase.Atoms`.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from io import StringIO
from itertools import count, islice
from pathlib import Path
from pprint import pprint
from typing import Any, Iterable, Iterator

import numpy as np

from . import cextxyz
from .grammar import (Properties, escape, extxyz_value_to_string, grammar,
                      result_to_dict)


@dataclass
class Frame:
    """One parsed extxyz frame, no ASE types.

    ``cell`` is the (3, 3) lattice as the comment line was written: rows are
    the ``Lattice="..."`` entries (so for ASE's column-vector convention the
    plugin transposes when constructing ``Atoms``).

    ``arrays`` keys use the *extxyz* column names (e.g. ``"species"``,
    ``"pos"``, ``"velo"``) — not the ASE-mapped names. Translation lives in
    the plugin layer.
    """
    natoms: int
    cell: np.ndarray
    pbc: np.ndarray
    info: dict[str, Any] = field(default_factory=dict)
    arrays: dict[str, np.ndarray] = field(default_factory=dict)


# ----------------------------------------------------------------------------
# Read path
# ----------------------------------------------------------------------------

def extract_lattice(result_dict):
    """Pop ``Lattice`` from ``result_dict`` and apply semantic shape conversions.

    Returns the (3, 3) lattice matrix or ``None`` if the key is absent.
    The matrix is in extxyz comment-line orientation; callers wanting ASE
    conventions should transpose.
    """
    try:
        lattice = result_dict.pop('Lattice')
    except KeyError:
        return None
    if lattice.shape == (3, 3):
        return lattice.astype(float)
    if lattice.shape == (3,):
        return np.diag(lattice).astype(float)
    if lattice.shape == (9,):
        return np.reshape(lattice, (3, 3), order='F').astype(float)
    raise ValueError(f'Lattice has wrong shape {lattice.shape}')


def read_comment_line(line, verbose=0):
    """Parse an extxyz comment line into a dict using pyleri."""
    result = grammar.parse(line)
    parsed_part = result.tree.children[0].string
    if not result.is_valid:
        raise SyntaxError(f"Failed to parse entire input line, only '{parsed_part}'. "
                          f'Expecting one of : {result.expecting}')
    return result_to_dict(result, verbose=verbose)


def _read_frame_pure_python(file, verbose=0, use_regex=True):
    """Read one extxyz frame from ``file`` using the pure-Python path.

    Returns ``(natoms, info_dict, structured_data, properties)``.
    Raises ``EOFError`` past the last frame.
    """
    file = iter(file)
    try:
        line = next(file)
    except StopIteration:
        raise EOFError()
    if re.match(r'^\s*$', line):
        raise EOFError()

    natoms = int(line)
    comment = next(file)
    info = read_comment_line(comment, verbose)
    if len(info) == 0:
        info['comment'] = comment.strip()
    if verbose:
        print('read_frame info = ')
        pprint(info)

    properties = info.pop('properties', 'species:S:1:pos:R:3')
    properties = Properties(property_string=properties)

    if use_regex:
        lines = [next(file) for _ in range(natoms)]
        buffer = StringIO(''.join(lines))
        data = np.fromregex(buffer, properties.regex, properties.dtype_scalar)
    else:
        data = np.genfromtxt(file, properties.dtype_vector, max_rows=natoms)

    return natoms, info, data, properties


def _read_frame_dict(file, *, use_cextxyz=True, use_regex=True, verbose=0,
                    comment=None) -> Frame | None:
    """Read one frame and return a :class:`Frame`, or ``None`` past EOF."""
    try:
        if use_cextxyz:
            try:
                fpos = cextxyz.cftell(file)
                natoms, info, arrays = cextxyz.read_frame_dicts(
                    file, verbose=verbose, comment=comment)
            except cextxyz.ExtXYZError as msg:
                error_message, = msg.args
                if error_message.startswith('Failed to parse string'):
                    cextxyz.cfseek(file, fpos, 0)
                    natoms, info, arrays = cextxyz.read_frame_dicts(
                        file, verbose=verbose,
                        comment="Properties=species:S:1:pos:R:3")
                else:
                    raise
            properties = info.pop('Properties', 'species:S:1:pos:R:3')
            properties = Properties(property_string=properties)
            data = np.zeros(natoms, properties.dtype_vector)
            for name, value in arrays.items():
                data[name] = value
        else:
            natoms, info, data, properties = _read_frame_pure_python(
                file, verbose=verbose, use_regex=use_regex)
    except EOFError:
        return None

    properties.data = data
    lattice = extract_lattice(info)

    arrays_out = {name: properties.data[name].copy()
                  for name in properties.dtype_vector.names}

    pbc = np.asarray(info.pop('pbc', [True, True, True]), dtype=bool)
    cell = lattice if lattice is not None else np.zeros((3, 3))

    return Frame(natoms=natoms, cell=cell, pbc=pbc, info=info, arrays=arrays_out)


def iread_dicts(file, index=None, *,
                use_cextxyz=True, use_regex=True, verbose=0, comment=None
                ) -> Iterator[Frame]:
    """Yield :class:`Frame` instances from ``file`` lazily.

    ``file`` may be a path (``str`` / ``Path``) or, for the pure-Python
    backend, an open text-mode file object.

    ``index`` accepts an int, a ``slice``, ``None`` (== all), or ``':'``.
    Negative indices are not supported.
    """
    own_fh = False
    if isinstance(file, (str, Path)):
        if use_cextxyz:
            file = cextxyz.cfopen(str(file), 'r')
            own_fh = True
        else:
            if file == '-':
                file = sys.stdin
            else:
                file = open(file, 'r')
                own_fh = True
    elif index is not None:
        raise ValueError('`index` argument cannot be used with open files')

    if index is None or index == ':':
        index = slice(None, None, None)
    if not isinstance(index, (slice, str)):
        index = slice(index, (index + 1) or None)
    if (index.start is not None and index.start < 0) or \
       (index.stop is not None and index.stop < 0):
        raise ValueError("Negative indices not (yet) supported in iread_dicts()")

    current_frame = 0
    frame_indices = islice(count(0), index.start, index.stop, index.step)
    try:
        for frame_idx in frame_indices:
            while current_frame <= frame_idx:
                f = _read_frame_dict(file, use_cextxyz=use_cextxyz,
                                     use_regex=use_regex, verbose=verbose,
                                     comment=comment)
                current_frame += 1
                if f is None:
                    break
            if f is None:
                break
            yield f
    finally:
        if own_fh:
            if use_cextxyz:
                cextxyz.cfclose(file)
            else:
                file.close()


def read_dicts(file, **kwargs):
    """Eager read: returns a single :class:`Frame` if the file has one frame,
    otherwise a list of :class:`Frame`.
    """
    frames = list(iread_dicts(file, **kwargs))
    if len(frames) == 1:
        return frames[0]
    return frames


# ----------------------------------------------------------------------------
# Write path
# ----------------------------------------------------------------------------

def _write_frame_python(file, frame: Frame, *, columns=None,
                        format_dict=None, verbose=0):
    """Write one Frame using the pure-Python writer."""
    if columns is None:
        # Force species/pos to come first if present.
        columns = list(frame.arrays.keys())
        for special in ('pos', 'species'):
            if special in columns:
                columns.remove(special)
        if 'species' in frame.arrays:
            columns.insert(0, 'species')
        if 'pos' in frame.arrays:
            insert_at = 1 if 'species' in frame.arrays else 0
            columns.insert(insert_at, 'pos')

    properties = []
    values = []
    for column in columns:
        value = frame.arrays[column]
        try:
            ptype = Properties.format_map[value.dtype.kind]
        except KeyError:
            if verbose:
                print(f'skipping "{column}" unsupported dtype.kind {value.dtype.kind}')
            continue
        if value.ndim == 1 or (value.ndim == 2 and value.shape[1] == 1):
            ncols = 1
        else:
            ncols = value.shape[1]
        properties.append((column, ptype, ncols))
        values.append(value)

    props = Properties(properties=properties, format_dict=format_dict)
    props._data = np.zeros(frame.natoms, props.dtype_vector)
    for name, value in zip(props, values):
        props._data[name] = value

    info = dict(frame.info)
    info['Lattice'] = frame.cell.T  # serialize column-major to match comment-line layout
    info['pbc'] = frame.pbc
    info['Properties'] = props.property_string

    file.write(f'{frame.natoms}\n')
    comment = ' '.join(f'{escape(k)}={extxyz_value_to_string(v)}' for k, v in info.items())
    file.write(comment + '\n')
    np.savetxt(file, props.data_columns, fmt=props.format_strings)


def _write_frame_cextxyz(c_file, frame: Frame, *, columns=None, verbose=0):
    """Write one Frame using the C writer."""
    info = dict(frame.info)
    info['Lattice'] = frame.cell.T  # match the column-major layout of comment-line Lattice="..."
    info['pbc'] = frame.pbc

    if columns is None:
        columns = list(frame.arrays.keys())
        for special in ('pos', 'species'):
            if special in columns:
                columns.remove(special)
        if 'species' in frame.arrays:
            columns.insert(0, 'species')
        if 'pos' in frame.arrays:
            insert_at = 1 if 'species' in frame.arrays else 0
            columns.insert(insert_at, 'pos')

    cextxyz.write_frame_dicts(c_file, frame.natoms, info,
                              {k: frame.arrays[k] for k in columns},
                              columns, verbose)


def write_dicts(file, frames: Frame | Iterable[Frame], *,
                use_cextxyz=True, append=False, columns=None,
                format_dict=None, verbose=0):
    """Write one or many :class:`Frame` to ``file``.

    ``file`` is a path (str/Path) or an open file object. The C writer
    requires a path (it opens the file via the same C runtime that owns the
    parser); passing an open Python file object falls back to the pure-Python
    writer regardless of ``use_cextxyz``.
    """
    if isinstance(frames, Frame):
        frames = [frames]

    own_fh = False
    mode = 'a' if append else 'w'

    if use_cextxyz and isinstance(file, (str, Path)):
        c_file = cextxyz.cfopen(str(file), mode)
        try:
            for frame in frames:
                if format_dict is not None:
                    raise ValueError('C writer does not support custom format strings')
                _write_frame_cextxyz(c_file, frame, columns=columns, verbose=verbose)
        finally:
            cextxyz.cfclose(c_file)
        return

    # pure-Python path; accept str/Path or open file object
    if isinstance(file, (str, Path)):
        if str(file) == '-':
            fh = sys.stdout
        else:
            fh = open(file, mode)
            own_fh = True
    else:
        fh = file
    try:
        for frame in frames:
            _write_frame_python(fh, frame, columns=columns,
                                format_dict=format_dict, verbose=verbose)
    finally:
        if own_fh:
            fh.close()
