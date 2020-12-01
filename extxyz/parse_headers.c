#include <stdio.h>
#include <cleri/cleri.h>
#include "extxyz_kv_grammar.h"

int main(int argc, char *argv[]) {
    FILE *fp;
    char line[10240];
    cleri_grammar_t * kv_grammar = compile_extxyz_kv_grammar();

    if (argc != 2) {
        fprintf(stderr, "Usage: %s in.xyz\n", argv[0]);
        exit(1);
    }

    fp = fopen(argv[1], "r");
    int nat = 0, counter = 0;
    while (fgets(line, 10239, fp)) {
        // printf("loop start counter %d line %s", counter, line);
        if (counter == 0) {
            sscanf(line, "%d", &nat);
            counter = nat+2;
        } else if (counter == nat+1) {
            cleri_parse_t * pr = cleri_parse(kv_grammar, line);
            // printf("Test: %s, '%s'\n", pr->is_valid ? "true" : "false", line);
            /* cleanup */
            cleri_parse_free(pr);
        }
        counter--;
    }

    cleri_grammar_free(kv_grammar);

    return 0;
}
