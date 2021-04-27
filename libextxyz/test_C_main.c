#include <stdio.h>
#include "extxyz_kv_grammar.h"
#include "extxyz.h"

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s filename verbose\n", argv[0]);
        exit(1);
    }
    FILE *fp = fopen(argv[1], "r");

    cleri_grammar_t *kv_grammar = compile_extxyz_kv_grammar();
    int nat;
    DictEntry *info, *arrays;

    int success = extxyz_read_ll(kv_grammar, fp, &nat, &info, &arrays);
    printf("parsed success %d\n", success);
    printf("nat %d\n", nat);
    printf("info\n");
    print_dict(info);
    printf("arrays\n");
    print_dict(arrays);

    int err_stat = extxyz_write_ll(stdout, nat, info, arrays);
    printf("written err_stat %d\n", err_stat);
}
