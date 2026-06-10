#ifndef EXTXYZ_FAST_FORMAT_H
#define EXTXYZ_FAST_FORMAT_H

// Bytes the caller must guarantee in `buf` passed to fmt_default_f16_8. The
// worst case is "%16.8f" of ~DBL_MAX (~318 chars); 512 is a comfortable bound.
#define FMT_F16_8_BUFSIZE 512

// Format `v` exactly as printf's "%16.8f" would, into `buf` (which must have at
// least FMT_F16_8_BUFSIZE bytes). Returns the number of bytes written (no
// terminating NUL is required by the caller).
//
// This is a fast, allocation-free replacement for snprintf on the writer's hot
// path. It is byte-for-byte identical to snprintf(buf, n, "%16.8f", v) for every
// double, using exact integer arithmetic (no rounding error) on platforms with
// 128-bit integers, and falling back to snprintf otherwise / for non-finite or
// out-of-range values.
int fmt_default_f16_8(char *buf, double v);

#endif
