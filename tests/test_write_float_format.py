"""The default writer's fast "%16.8f" float formatter must be byte-identical to
snprintf, validated end-to-end through the real C writer.

Trick: writing with the *default* format uses the fast exact integer formatter,
while writing the same frame with an explicit ``format_dict={'R': '%16.8f'}``
forces the snprintf path (a non-NULL custom format). The two byte streams must be
identical — so any rounding/format discrepancy in the fast path shows up here,
for whatever floats we feed in.
"""
import numpy as np

from extxyz import Frame, write_dicts


def _frame_with_floats(vals):
    vals = np.asarray(vals, dtype=float)
    n = len(vals)
    return Frame(natoms=n, cell=np.eye(3), pbc=np.array([False, False, False]),
                 info={}, arrays={"species": np.array(["X"] * n),
                                  "val": vals.reshape(n, 1)})


def _write_both(tmp_path, vals):
    f = _frame_with_floats(vals)
    a, b = tmp_path / "default.xyz", tmp_path / "snprintf.xyz"
    write_dicts(a, [f], use_cextxyz=True)                                # fast formatter
    write_dicts(b, [f], use_cextxyz=True, format_dict={"R": "%16.8f"})   # snprintf
    return a.read_bytes(), b.read_bytes()


EDGES = [
    0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 0.1, 0.2, 0.3,
    12.031073044999999,                      # round-half-to-even tie
    19.00927393, -0.00623274,
    1e-9, 1e-8, 1e-7, 1e-6, 1e6, 1e12, 1e14, 9.99999e14,
    123456789.12345678, -987654321.87654321,
    5e-324, 1e-300, -1e-300,                 # subnormals -> "0.00000000"
    0.030000005, 0.045000005, 0.055000005,   # more ties
]


def test_edges_match_snprintf(tmp_path):
    a, b = _write_both(tmp_path, EDGES)
    assert a == b


def test_random_matches_snprintf(tmp_path):
    rng = np.random.default_rng(12345)
    vals = np.concatenate([
        rng.uniform(-1e6, 1e6, 150000),      # typical magnitudes
        rng.uniform(-1.0, 1.0, 100000),      # small (lots of fractional digits)
        rng.uniform(-1e14, 1e14, 50000),     # near the fast-path ceiling
    ])
    a, b = _write_both(tmp_path, vals)
    assert a == b


def test_out_of_range_falls_back_and_matches(tmp_path):
    # |v| >= 1e15, inf, nan all take the snprintf fallback in the fast path too,
    # so default and explicit must still agree.
    vals = [1e15, -1e15, 1e16, 1e300, -1e300, np.inf, -np.inf, np.nan]
    a, b = _write_both(tmp_path, vals)
    assert a == b
