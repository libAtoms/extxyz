# ase-extxyz

ASE I/O plugin that wires the [`extxyz`](https://github.com/libAtoms/extxyz)
C parser into ASE's `read` / `write` machinery.

## Install

```bash
pip install ase-extxyz
```

This pulls in `extxyz` (the parser, with native binary wheels) and `ase`.

## Use

```python
import ase.io
from ase.build import bulk

atoms = bulk('Cu') * 2
ase.io.write('out.xyz', atoms, format='cextxyz')
back = ase.io.read('out.xyz', format='cextxyz')
```

The plugin registers a format named `cextxyz` (not `extxyz` — that name is
already taken by ASE's built-in regex-based reader). Pass `format='cextxyz'`
explicitly; auto-detection by extension is intentionally disabled to avoid
clashing with the built-in.

## Streaming output during optimization / MD

For long runs you don't want to reopen the file on every step. Use
`ExtXYZTrajectoryWriter` — it opens the libc `FILE*` once and writes
each frame through the C writer directly:

```python
from ase.optimize import LBFGS
from ase_extxyz.io import ExtXYZTrajectoryWriter

with ExtXYZTrajectoryWriter('opt.xyz', atoms=atoms) as traj:
    opt = LBFGS(atoms)
    opt.attach(traj, interval=1)   # opt calls traj() per step
    opt.run(fmax=1e-3)
```

`opt.attach(traj)` works because the writer is callable; `traj()` is
equivalent to `traj.write(atoms)` using the atoms captured at construction.

## What this is *not*

`ase-extxyz` is a thin translation layer between `extxyz.Frame` (a
plain-Python dict + numpy dataclass) and `ase.Atoms`. The fast C parser
lives in the `extxyz` package; install that alone if you don't need ASE.

## License

MIT — same as `extxyz`.
