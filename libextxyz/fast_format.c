#include <stdio.h>
#include <string.h>
#include <stdint.h>

#include "fast_format.h"

// Exact, allocation-free "%16.8f". printf's %.8f is the value rounded to 8
// fractional decimals with round-half-to-even (the default FP rounding mode,
// which this library never changes). A finite double is |v| = m * 2^e exactly,
// and 10^8 = 2^8 * 5^8, so
//     v * 10^8 = m * 5^8 * 2^(e+8) = m * 390625 * 2^(e+8)
// is an exact rational. We round that to the nearest integer (ties to even)
// using only integer arithmetic — no floating-point error — so the result is
// bit-for-bit what snprintf produces. 128-bit ints hold m*390625 (< 2^72);
// where they're unavailable (MSVC), or for non-finite / out-of-range inputs, we
// fall back to snprintf, which is identical (just not faster).
//
// No <math.h> (so no libm link dependency): finiteness, sign and magnitude all
// come from the IEEE-754 bit pattern we decode anyway.
int fmt_default_f16_8(char *buf, double v) {
#ifdef __SIZEOF_INT128__
    union { double d; uint64_t u; } un;
    un.d = v;
    int neg = (int)(un.u >> 63);                       // signbit (so -0.0 keeps '-')
    uint64_t bits = un.u & 0x7FFFFFFFFFFFFFFFULL;       // |v|
    int exp = (int)((bits >> 52) & 0x7FF);
    union { uint64_t u; double d; } ab;
    ab.u = bits;                                        // |v| as a double

    // fast path: finite (exp != 0x7FF) and |v| < 1e15 (so e <= -3, e+8 <= 5:
    // the left-shift can't overflow 128 bits and the integer part fits uint64).
    if (exp != 0x7FF && ab.d < 1e15) {
        uint64_t frac = bits & 0xFFFFFFFFFFFFFULL;
        uint64_t m;
        int e;
        if (exp == 0) { m = frac; e = -1074; }              // subnormal / zero
        else { m = frac | 0x10000000000000ULL; e = exp - 1075; }   // normal (implicit bit)

        unsigned __int128 N = (unsigned __int128)m * 390625u;   // m * 5^8
        unsigned __int128 scaled;
        int s = e + 8;
        if (s >= 0) {
            scaled = N << s;                                // exact (s <= 5 here)
        } else {
            int j = -s;                                     // > 0
            if (j >= 128) {
                scaled = 0;                                 // N < 2^72 << 2^j -> rounds to 0
            } else {
                unsigned __int128 q = N >> j;
                unsigned __int128 r = N & (((unsigned __int128)1 << j) - 1);
                unsigned __int128 half = (unsigned __int128)1 << (j - 1);
                if (r > half) q += 1;
                else if (r == half) q += (unsigned)(q & 1);   // ties to even
                scaled = q;
            }
        }

        uint64_t ip = (uint64_t)(scaled / 100000000ULL);
        uint64_t fp = (uint64_t)(scaled % 100000000ULL);

        // build "<ip>.<fp:08>" left-to-right into d
        char d[40];
        int dn = 0;
        char rev[24];
        int rn = 0;
        if (ip == 0) rev[rn++] = '0';
        else while (ip) { rev[rn++] = (char)('0' + (int)(ip % 10)); ip /= 10; }
        while (rn) d[dn++] = rev[--rn];
        d[dn++] = '.';
        for (int i = 7; i >= 0; i--) { d[dn + i] = (char)('0' + (int)(fp % 10)); fp /= 10; }
        dn += 8;

        int total = dn + neg;
        int pad = 16 - total;
        if (pad < 0) pad = 0;
        int n = 0;
        while (pad--) buf[n++] = ' ';
        if (neg) buf[n++] = '-';
        memcpy(buf + n, d, (size_t)dn);
        return n + dn;
    }
#endif
    return snprintf(buf, FMT_F16_8_BUFSIZE, "%16.8f", v);
}
