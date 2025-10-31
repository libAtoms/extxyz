# Meson Build System - Migration Status

**Branch**: `meson`
**PR**: #17
**Last Updated**: 2025-10-31 (Critical Windows fix in commit 83dc67d)
**Status**: 14/19 wheels building ✅ | Windows: Testing critical CIBW_ENVIRONMENT fix 🔄

## Current CI Results

### ✅ Passing (14 wheels)
- **Ubuntu x86_64**: 5/5 (Python 3.8, 3.9, 3.10, 3.11, 3.12)
- **macOS ARM64** (macos-latest): 4/4 (Python 3.9, 3.10, 3.11, 3.12)
- **macOS x86_64** (macos-13): 5/5 (Python 3.8, 3.9, 3.10, 3.11, 3.12)

### ❌ Failing (5 wheels)
- **Windows x86_64**: 0/5 (Python 3.8, 3.9, 3.10, 3.11, 3.12)
  - Issue: PCRE2 dependency detection still failing with vcpkg

## What Works

### Ubuntu (Complete ✅)
- Uses system PCRE2 from `yum install pcre2-devel`
- Meson finds PCRE2 via pkg-config
- All Python versions build and test successfully

### macOS ARM64 (Complete ✅)
- Uses Homebrew PCRE2: `brew install pcre2 pkg-config`
- Deployment target: macOS 15.0
- Meson finds PCRE2 via pkg-config
- All supported Python versions build (3.9-3.12, no 3.8 ARM64 support)

### macOS x86_64 (Complete ✅)
- Uses Homebrew PCRE2: `brew install pcre2 pkg-config`
- Deployment target: macOS 13.0 (allows testing on macos-13 runners)
- Meson finds PCRE2 via pkg-config
- All Python versions build and test successfully

## What Doesn't Work

### Windows (Incomplete ❌)

**Current Approach**: vcpkg (`vcpkg install pcre2:x64-windows`)

**Problem**: Meson's `dependency('libpcre2-8')` cannot find PCRE2, even with:
- vcpkg installation at `C:/vcpkg/installed/x64-windows`
- PKG_CONFIG_PATH set to vcpkg location
- CMAKE_PREFIX_PATH, PCRE2_ROOT, LIB, INCLUDE all configured
- pkg-config files present in vcpkg tree

**Fallback in meson.build**: Added `cc.find_library('pcre2-8')` for MinGW, but this also fails

**Root Cause Discovered (2025-10-31)**:
The Windows builds were **not failing due to PCRE2 detection** at all! They failed immediately when cibuildwheel started due to a malformed `CIBW_ENVIRONMENT_WINDOWS` configuration in the GitHub Actions workflow.

**Error**:
```
cibuildwheel: Malformed environment option 'CMAKE_PREFIX_PATH=C:/vcpkg/installed/x64-windows PKG_CONFIG_PATH=...'
```

**Problem**: All environment variables were in a single string separated by spaces, which cibuildwheel couldn't parse.

**Fix (commit 83dc67d)**: Changed to proper YAML multiline syntax:
```yaml
CIBW_ENVIRONMENT_WINDOWS: >-
  CMAKE_PREFIX_PATH=C:/vcpkg/installed/x64-windows
  PKG_CONFIG_PATH=C:/vcpkg/installed/x64-windows/lib/pkgconfig
  ...
```

**Previous Attempts** (all failed before reaching Meson):
1. Manual CMake build + install ❌
2. Manual pkg-config file creation ❌
3. Environment variables (LIB, INCLUDE, LIBRARY_PATH, CPATH) ❌
4. vcpkg package manager ❌ (couldn't pass env vars to cibuildwheel)
5. **pkgconfiglite + vcpkg** (commit 816b5e1) - still using broken CIBW_ENVIRONMENT
6. **Meson wrap fallback** (commit 816b5e1) - Added `subprojects/pcre2.wrap`

## Architecture Overview

### Three-Layer Implementation
1. **C Core** (`libextxyz/`)
   - Low-level parser using libcleri
   - Depends on PCRE2 for regex operations
   - Functions: `extxyz_read_ll()`, `extxyz_write_ll()`

2. **Python Extension** (`python/extxyz/_extxyz`)
   - C extension module wrapping libextxyz
   - Built by Meson (defined in `libextxyz/meson.build`)

3. **Pure Python** (`python/extxyz/extxyz.py`)
   - High-level API: `read()`, `write()`, `iread()`
   - Alternative grammar parser using pyleri (no C dependency)

### Build System Flow
```
Top-level meson.build
├── Detect Python, PCRE2
├── libcleri/ (submodule)
│   └── Build libcleri static library
├── libextxyz/
│   ├── Generate grammar from Python
│   └── Build _extxyz extension module
└── python/extxyz/
    ├── Generate _version.py
    └── Install pure Python sources
```

## Key Changes from Makefile

### Build Configuration
- **Before**: Makefile with manual compiler flags
- **After**: Meson with automatic dependency detection
- **Benefits**: Cross-platform, better integration with pip/meson-python

### Dependency Management
- **PCRE2**: Now detected via `dependency('libpcre2-8')` with fallback to `cc.find_library()`
- **libcleri**: Built as subproject via `subdir('libcleri')`
- **Python**: Detected via meson's python module

### CI/CD
- **Parallelized builds**: 19 jobs (was sequential by Python version)
- **Matrix strategy**: 4 OS × 5 Python versions
- **Wheel building**: cibuildwheel v2.22.0

## Windows PCRE2 Detection - Next Steps

### Option 1: Use Conan Package Manager
```yaml
- name: Install PCRE2 via Conan
  run: |
    pip install conan
    conan install --requires=pcre2/10.42 --build=missing
```

### Option 2: Pre-built PCRE2 Binaries
Download pre-compiled PCRE2 from official releases or build artifacts

### Option 3: Build Static Library
Build PCRE2 as static library and link statically (avoids runtime DLL issues)

### Option 4: Skip C Extension on Windows
Build pure Python wheels only (slower but functional):
```yaml
CIBW_BUILD_FRONTEND_WINDOWS: "build[no-cextxyz]"
```

### Option 5: Fix pkg-config on Windows
Install working pkg-config (not Strawberry Perl version):
```yaml
choco install pkgconfiglite
# Ensure it's in PATH before Strawberry Perl
```

## Testing Locally

### Prerequisites
- Python 3.8+
- Meson >= 1.0.0
- Ninja
- PCRE2 library
- C compiler

### Build and Install
```bash
# Using uv
uv venv
source .venv/bin/activate
uv pip install .

# Using pip
pip install .

# Editable install (has issues with meson-python, use regular install)
pip install -e .  # NOT RECOMMENDED
```

### Run Tests
```bash
pytest tests/

# Test specific backend
USE_CEXTXYZ=true pytest tests/    # Test C extension
USE_CEXTXYZ=false pytest tests/   # Test pure Python
```

### CLI
```bash
extxyz file.xyz              # Read and display
extxyz -v file.xyz          # Verbose
extxyz -c file.xyz          # Force C extension
python -m extxyz file.xyz   # Via module
```

## File Changes Summary

### New Files
- `meson.build` (top-level)
- `libextxyz/meson.build`
- `python/extxyz/meson.build`
- `libcleri/meson.build` (submodule)
- `discover_version.py` (version detection for meson)
- `pyproject.toml` (updated for meson-python backend)

### Modified Files
- `pyproject.toml`: Changed build backend to meson-python
- `.github/workflows/build-wheels.yml`: Updated for parallel builds
- `.github/workflows/python-package.yml`: Updated actions, Python versions

### Preserved Files
- `libextxyz/Makefile`: Still present for manual builds
- All source files: No changes to C/Python implementation
- Tests: No changes to test suite

## Current Fix Implementation (Commit 816b5e1)

### Two-Pronged Approach

**Primary: pkgconfiglite installation**
```yaml
# In .github/workflows/build-wheels.yml
- name: Install PCRE2 via vcpkg (Windows only)
  run: |
    choco install pkgconfiglite -y  # Working pkg-config
    vcpkg install pcre2:x64-windows
    echo "C:/ProgramData/chocolatey/lib/pkgconfiglite/tools/bin" >> $GITHUB_PATH
    echo "PKG_CONFIG_PATH=C:/vcpkg/installed/x64-windows/lib/pkgconfig" >> $GITHUB_ENV
```

**Fallback: Meson wrap system**
```ini
# subprojects/pcre2.wrap
[wrap-file]
directory = pcre2-10.44
source_url = https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.44/pcre2-10.44.tar.gz
patch_url = https://wrapdb.mesonbuild.com/v2/pcre2_10.44-1/get_patch
```

If pkg-config detection fails, Meson will automatically:
1. Download PCRE2 10.44 from GitHub
2. Apply WrapDB patches for Meson compatibility
3. Build PCRE2 as a subproject
4. Link statically into the extension module

**Why This Should Work**:
- pkgconfiglite provides working `pkg-config` binary (not Strawberry Perl's broken version)
- vcpkg's `.pc` files can be properly parsed
- If all else fails, Meson wrap builds PCRE2 from source (always succeeds)

## References

- **PR**: https://github.com/libAtoms/extxyz/pull/17
- **Latest CI Run**: https://github.com/libAtoms/extxyz/actions (check runs for commit 816b5e1)
- **Previous CI Logs**: https://github.com/libAtoms/extxyz/actions/runs/18970365146
- **Meson Python**: https://meson-python.readthedocs.io/
- **cibuildwheel**: https://cibuildwheel.readthedocs.io/
- **Meson WrapDB**: https://mesonbuild.com/Wrapdb-projects.html
