#!/usr/bin/env bash
#
# Build a static PCRE2 for macOS wheels at the wheel's deployment target.
#
# Homebrew's PCRE2 bottle is compiled for the build runner's macOS (e.g. 15.0 or
# newer), so linking/bundling it produces a wheel that fails to load on older macOS
# even when the wheel is tagged for an older target. We therefore build PCRE2 from
# source here, statically, at $MACOSX_DEPLOYMENT_TARGET, and expose it via
# PKG_CONFIG_PATH (see pyproject.toml). meson then links it into _extxyz.so, so the
# wheel ships only the extension module with no bundled dylib.
#
# Run by cibuildwheel's before-all step on macOS (both arm64 and x86_64).
set -euo pipefail

PCRE2_VERSION="10.44"   # keep in sync with subprojects/pcre2.wrap
PREFIX="/tmp/pcre2"
: "${MACOSX_DEPLOYMENT_TARGET:=11.0}"
export MACOSX_DEPLOYMENT_TARGET

brew install pkg-config

curl -fL "https://github.com/PCRE2Project/pcre2/releases/download/pcre2-${PCRE2_VERSION}/pcre2-${PCRE2_VERSION}.tar.bz2" \
  -o /tmp/pcre2.tar.bz2
rm -rf /tmp/pcre2src && mkdir -p /tmp/pcre2src
tar xjf /tmp/pcre2.tar.bz2 -C /tmp/pcre2src --strip-components=1

cd /tmp/pcre2src
./configure \
  --prefix="${PREFIX}" \
  --enable-static \
  --disable-shared \
  --with-pic \
  --enable-jit \
  --quiet
make -j3
make install
