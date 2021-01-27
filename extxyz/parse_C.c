#include <stdio.h>
#include <cleri/cleri.h>
#include "extxyz_kv_grammar.h"
#include "extxyz.h"

int main(int argc, char *argv[]) {
    FILE *fp;
    char line[10240];

    cleri_grammar_t * kv_grammar = compile_extxyz_kv_grammar();

    if (argc != 2) {
        fprintf(stderr, "Usage: %s in.xyz\n", argv[0]);
        exit(1);
    }

    int n_config = 0;

    DictEntry *info;
    Arrays *arrays;
    fp = fopen(argv[1], "r");
    while (extxyz_read_ll(kv_grammar, fp, &info, &arrays)) {

        // print summary of info and arrays
        print_info_arrays(info, arrays);

        free_arrays(arrays);
        free_info(info);

        n_config++;
        if (n_config % 1000 == 0) {
            fprintf(stderr, ".");
            fflush(stderr);
        }
    }
    fprintf(stderr, "\n");

    cleri_grammar_free(kv_grammar);

    return 0;
}
