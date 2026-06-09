"""Robustness tests for the C backend (cextxyz).

Several of these exercise inputs that previously crashed the C parser with a
segmentation fault. A crash takes the whole interpreter down, so each parse is
run in a *subprocess*: the test asserts the child exits gracefully (catching
``ExtXYZError``/``EOFError`` or parsing successfully) rather than dying on
SIGSEGV/SIGABRT.
"""
import signal
import subprocess
import sys
import textwrap

import pytest

CRASH_SIGNALS = {-signal.SIGSEGV, -signal.SIGABRT, -signal.SIGBUS}


def _run_cextxyz_parse(tmp_path, content):
    """Parse ``content`` with the C backend in a subprocess.

    Returns the CompletedProcess. The child exits 0 on a graceful outcome
    (parsed, or raised ExtXYZError/EOFError), and non-zero on any other Python
    exception. A negative returncode means it was killed by a signal (crash).

    The child inherits this process's environment, so it imports the same
    ``extxyz`` we do (the installed package in CI, or a source tree on
    ``PYTHONPATH`` locally) -- we must NOT force the source dir onto the path,
    as it lacks the build-generated ``extxyz._version``.
    """
    xyz = tmp_path / "in.xyz"
    xyz.write_text(content)
    child = textwrap.dedent(
        f"""
        import sys
        from extxyz import read_dicts
        from extxyz.cextxyz import ExtXYZError
        try:
            read_dicts({str(xyz)!r}, use_cextxyz=True)
        except (ExtXYZError, EOFError) as e:
            print("GRACEFUL", type(e).__name__)
            sys.exit(0)
        except Exception as e:  # noqa: BLE001
            print("PYEXC", type(e).__name__, e)
            sys.exit(0)
        print("PARSED-OK")
        sys.exit(0)
        """
    )
    return subprocess.run(
        [sys.executable, "-c", child],
        capture_output=True, text=True, timeout=30,
    )


LATTICE = 'Lattice="2 0 0 0 2 0 0 0 2"'


@pytest.mark.parametrize("props", [
    "species",          # no type, no count -> strtok(NULL) on type
    "species:S",        # no count -> strtok(NULL) on count
    "species:S:",       # empty count
    "pos:R:3:species",  # trailing property name with no type/count
])
def test_malformed_properties_does_not_crash(tmp_path, props):
    content = f"1\n{LATTICE} Properties={props}\nH 0.0 0.0 0.0\n"
    proc = _run_cextxyz_parse(tmp_path, content)
    assert proc.returncode not in CRASH_SIGNALS, (
        f"C parser crashed (signal {-proc.returncode}) on Properties={props!r}\n"
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    # must be a clean, well-formed error, not an unrelated Python crash
    assert proc.returncode == 0, (proc.stdout, proc.stderr)


def test_truncated_file_errors_cleanly(tmp_path):
    """natoms claims more rows than present -> the C parser bails after info and
    arrays are built (it frees the partial dicts; verified separately via
    `leaks`). The high-level read treats the short frame as EOF, so this must
    finish cleanly without crashing."""
    content = f"3\n{LATTICE} Properties=species:S:1:pos:R:3\nH 0 0 0\n"
    proc = _run_cextxyz_parse(tmp_path, content)
    assert proc.returncode not in CRASH_SIGNALS, (proc.stdout, proc.stderr)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)


def test_grammar_freed_at_exit_does_not_crash(tmp_path):
    """The cached cleri grammar is freed via atexit; a process that imports the
    C backend, parses, and exits must do so cleanly (exit 0, no crash from a
    double free). Verifies the leak fix doesn't introduce a teardown crash.
    """
    xyz = tmp_path / "g.xyz"
    xyz.write_text(f"1\n{LATTICE} Properties=species:S:1:pos:R:3\nH 0 0 0\n")
    child = textwrap.dedent(
        f"""
        from extxyz import read_dicts
        from extxyz import cextxyz
        read_dicts({str(xyz)!r}, use_cextxyz=True)
        # calling the atexit handler explicitly must be idempotent/safe
        cextxyz._free_kv_grammar()
        cextxyz._free_kv_grammar()
        print("OK")
        """
    )
    proc = subprocess.run([sys.executable, "-c", child],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "OK" in proc.stdout


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_space_padded_data_rows(tmp_path, use_cextxyz):
    """The Rust port claims (in its own TODO, unverified) that 'array rows with
    space padding cause segfault'. They don't: the per-atom regex is
    ``^\\s*(...)\\s+...\\s*$``. This locks in that leading, extra inter-column,
    and trailing whitespace in data rows parse correctly on both backends.
    """
    import numpy as np
    from extxyz import read_dicts
    content = (
        "2\n"
        f"{LATTICE} Properties=species:S:1:pos:R:3\n"
        "   H    0.0   1.0    2.0   \n"      # leading + extra + trailing spaces
        "\tO\t3.0\t4.0\t5.0\t\n"             # tabs as separators/padding
    )
    p = tmp_path / "padded.xyz"
    p.write_text(content)
    frame = read_dicts(p, use_cextxyz=use_cextxyz)
    assert frame.natoms == 2
    assert list(frame.arrays["species"]) == ["H", "O"]
    np.testing.assert_allclose(
        frame.arrays["pos"], [[0, 1, 2], [3, 4, 5]], atol=1e-7)


@pytest.mark.parametrize("use_cextxyz", [False, True])
def test_leading_whitespace_on_info_line(tmp_path, use_cextxyz):
    """An info/comment line that begins with whitespace must still parse.

    The Rust port advertises this ("accept leading spaces for each line"); the
    natoms line and per-atom rows already tolerate it, only the info line did
    not on the C backend.
    """
    from extxyz import read_dicts
    content = (
        "1\n"
        f"   {LATTICE} Properties=species:S:1:pos:R:3 energy=-1.5\n"
        "H 0.0 0.0 0.0\n"
    )
    p = tmp_path / "leading.xyz"
    p.write_text(content)
    frame = read_dicts(p, use_cextxyz=use_cextxyz)
    assert frame.natoms == 1
    assert frame.info["energy"] == pytest.approx(-1.5)
    assert "species" in frame.arrays and "pos" in frame.arrays
