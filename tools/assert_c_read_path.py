"""Fail if the installed _extxyz lacks the C-API fast read path.

Every CI-built wheel is built with numpy in the build environment, so
``cextxyz._HAVE_C_READ`` must be True. A False here means the wheel silently
fell back to the slower ctypes marshalling (e.g. numpy headers were missing at
build time, or PyInit__extxyz wasn't exported) — which we want to catch loudly
rather than ship a quietly-slow wheel. Run as part of cibuildwheel's
test-command.
"""
import sys

from extxyz import cextxyz

if not cextxyz._HAVE_C_READ:
    sys.exit("ERROR: _extxyz was built without the C-API fast read path; "
             "the package fell back to the ctypes marshalling. Check that "
             "numpy headers were available at build time (and, on Windows, "
             "that PyInit__extxyz is exported in _extxyz_pyext.def).")
print("OK: _extxyz C-API fast read path is active (cextxyz._HAVE_C_READ=True)")
