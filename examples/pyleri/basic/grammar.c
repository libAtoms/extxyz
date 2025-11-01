/*
 * grammar.c
 *
 * This grammar is generated using the Grammar.export_c() method and
 * should be used with the libcleri module.
 *
 * Source class: MyGrammar
 * Created at: 2020-10-30 14:47:45
 */

#include "grammar.h"
#include <stdio.h>

#define CLERI_CASE_SENSITIVE 0
#define CLERI_CASE_INSENSITIVE 1

#define CLERI_FIRST_MATCH 0
#define CLERI_MOST_GREEDY 1

cleri_grammar_t * compile_grammar(void)
{
    cleri_t * r_name = cleri_regex(CLERI_GID_R_NAME, "^(?:\"(?:[^\"]*)\")+");
    cleri_t * k_hi = cleri_keyword(CLERI_GID_K_HI, "hi", CLERI_CASE_SENSITIVE);
    cleri_t * START = cleri_sequence(
        CLERI_GID_START,
        2,
        k_hi,
        r_name
    );

    cleri_grammar_t * grammar = cleri_grammar(START, "^\\w+");

    return grammar;
}
