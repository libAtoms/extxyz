#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "extxyz_kv_grammar.h"
#include "extxyz.h"

int main(int argc, char *argv[]) {
    if (argc < 3 || argc > 5) {
        fprintf(stderr, "Usage: %s filename verbose [tok] [disp]\n", argv[0]);
        exit(1);
    }
    FILE *fp = fopen(argv[1], "r");
    if (! fp) {
        fprintf(stderr, "ERROR: could not open '%s'\n", argv[1]);
        exit(1);
    }

    cleri_grammar_t *kv_grammar = compile_extxyz_kv_grammar();
    int nat;
    DictEntry *info, *arrays;

    // NULL comment => parse the comment line read from the file.
    // error_message must be a buffer: extxyz_read_ll sprintf()s into it.
    char *comment = NULL;
    char error_message[1024] = "";

    int verbose = ! strcmp(argv[2], "T");
    // optional 3rd arg "tok"/"T" selects the whitespace tokenizer over the regex
    int use_tokenizer = (argc >= 4 && (! strcmp(argv[3], "tok") || ! strcmp(argv[3], "T")));
    // optional 4th arg "disp" selects the first-char-dispatch comment parser
    int use_cleri = ! (argc == 5 && ! strcmp(argv[4], "disp"));
    int success = extxyz_read_ll_opts(kv_grammar, fp, &nat, &info, &arrays, comment, error_message, use_tokenizer, use_cleri);
    if (! success) {
        fprintf(stderr, "ERROR parsing '%s': %s\n", argv[1], error_message);
    } else {
        if (verbose) {
            printf("parsed success %d\n", success);
            printf("nat %d\n", nat);
            printf("info\n");
            print_dict(info);
            printf("arrays\n");
            print_dict(arrays);
        }
        int err_stat = extxyz_write_ll(stdout, nat, info, arrays);
        if (verbose) {
            printf("written err_stat %d\n", err_stat);
        }
        free_dict(info);
        free_dict(arrays);
    }

    cleri_grammar_free(kv_grammar);
    fclose(fp);
    return success ? 0 : 1;
}
