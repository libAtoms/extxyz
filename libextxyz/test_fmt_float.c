// Exhaustive validation: fmt_default_f16_8(v) must be byte-for-byte identical to
// snprintf(buf, n, "%16.8f", v) for every double. The naive scaled-integer
// rounding (v*1e8 + 0.5) disagrees with printf's round-half-to-even ~1 in 5e6
// values, so this loops over tens of millions of inputs — uniform random across
// magnitudes plus targeted sweeps near rounding ties and known edge cases.
//
// Exit status 0 = all matched; 1 = at least one mismatch (printed).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <float.h>

#include "fast_format.h"

static uint64_t rng_state = 0x123456789abcdef0ULL;
static uint64_t xorshift(void) {
    uint64_t x = rng_state;
    x ^= x << 13; x ^= x >> 7; x ^= x << 17;
    return rng_state = x;
}

static long mism = 0, checked = 0;

static int check(double v) {
    char a[FMT_F16_8_BUFSIZE], b[FMT_F16_8_BUFSIZE];
    snprintf(a, sizeof a, "%16.8f", v);
    int n = fmt_default_f16_8(b, v);
    b[n] = 0;
    checked++;
    if (strcmp(a, b) != 0) {
        if (mism < 20)
            printf("  MISMATCH: printf[%s] fast[%s] (v=%.17g, len=%d)\n", a, b, v, n);
        mism++;
        return 1;
    }
    return 0;
}

int main(int argc, char **argv) {
    long N = (argc > 1) ? atol(argv[1]) : 50000000L;

    // 1. targeted edge cases
    double edges[] = {
        0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 0.1, 0.2, 0.3,
        12.031073044999999,            // known naive-vs-printf tie mismatch
        19.00927393, -0.00623274,
        DBL_MIN, -DBL_MIN, 1e-300, -1e-300, 4.9e-324,   // subnormals
        1e-9, 1e-8, 1e-7, 9.999999995e-1,
        1e6, 1e9, 1e12, 1e14, 1e15 - 1, 9.99999e14,
        123456789.12345678, -987654321.87654321,
    };
    for (size_t i = 0; i < sizeof(edges)/sizeof(edges[0]); i++) check(edges[i]);

    // 2. dense sweep straddling 8th-decimal ties: k + 0.5e-8 and neighbours
    for (long k = 0; k < 2000000; k++) {
        double base = (double)k * 1e-2;
        check(base + 0.5e-8);
        check(base + 0.5e-8 + 1e-17);
        check(base + 0.5e-8 - 1e-17);
    }

    // 3. uniform random doubles across magnitudes in the fast range
    for (long i = 0; i < N; i++) {
        uint64_t r = xorshift();
        // random sign, magnitude spread over [1e-12, ~1e14]
        double mant = (double)(r >> 11) / (double)(1ULL << 53);   // [0,1)
        int exp = -40 + (int)(xorshift() % 90);                    // 2^-40 .. 2^50
        double v = ldexp(mant, exp);
        if (xorshift() & 1) v = -v;
        check(v);
    }

    printf("checked %ld values, %ld mismatches\n", checked, mism);
    return mism ? 1 : 0;
}
