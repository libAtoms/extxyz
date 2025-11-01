/*
 * grammar.c
 *
 * This grammar is generated using the Grammar.export_c() method and
 * should be used with the libcleri module.
 *
 * Source class: ExtxyzKVGrammar
 * Created at: 2020-11-27 14:56:41
 */

#include "grammar.h"
#include <stdio.h>

#define CLERI_CASE_SENSITIVE 0
#define CLERI_CASE_INSENSITIVE 1

#define CLERI_FIRST_MATCH 0
#define CLERI_MOST_GREEDY 1

cleri_grammar_t * compile_grammar(void)
{
    cleri_t * r_barestring = cleri_regex(CLERI_GID_R_BARESTRING, "^(?:[^\\s=\'\",}{\\]\\[\\\\]|(?:\\\\[\\s=\'\",}{\\]\\]\\\\]))+");
    cleri_t * r_quotedstring = cleri_regex(CLERI_GID_R_QUOTEDSTRING, "^(\")(?:(?=(\\\\?))\\2.)*?\\1");
    cleri_t * r_string = cleri_choice(
        CLERI_GID_R_STRING,
        CLERI_MOST_GREEDY,
        2,
        r_barestring,
        r_quotedstring
    );
    cleri_t * r_integer = cleri_regex(CLERI_GID_R_INTEGER, "^[+-]?[0-9]+");
    cleri_t * r_float = cleri_regex(CLERI_GID_R_FLOAT, "^[+-]?(?:[0-9]+[.]?[0-9]*|\\.[0-9]+)(?:[dDeE][+-]?[0-9]+)?");
    cleri_t * k_true = cleri_keyword(CLERI_GID_K_TRUE, "T", CLERI_CASE_SENSITIVE);
    cleri_t * k_false = cleri_keyword(CLERI_GID_K_FALSE, "F", CLERI_CASE_SENSITIVE);
    cleri_t * ints = cleri_list(CLERI_GID_INTS, r_integer, cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * floats = cleri_list(CLERI_GID_FLOATS, r_float, cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * bools = cleri_list(CLERI_GID_BOOLS, cleri_choice(
        CLERI_NONE,
        CLERI_MOST_GREEDY,
        2,
        k_true,
        k_false
    ), cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * strings = cleri_list(CLERI_GID_STRINGS, r_string, cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * ints_sp = cleri_repeat(CLERI_GID_INTS_SP, r_integer, 1, 0);
    cleri_t * floats_sp = cleri_repeat(CLERI_GID_FLOATS_SP, r_float, 1, 0);
    cleri_t * bools_sp = cleri_repeat(CLERI_GID_BOOLS_SP, cleri_choice(
        CLERI_NONE,
        CLERI_MOST_GREEDY,
        2,
        k_true,
        k_false
    ), 1, 0);
    cleri_t * strings_sp = cleri_repeat(CLERI_GID_STRINGS_SP, r_string, 1, 0);
    cleri_t * old_one_d_array = cleri_choice(
        CLERI_GID_OLD_ONE_D_ARRAY,
        CLERI_MOST_GREEDY,
        2,
        cleri_sequence(
            CLERI_NONE,
            3,
            cleri_token(CLERI_NONE, """),
            cleri_choice(
                CLERI_NONE,
                CLERI_MOST_GREEDY,
                3,
                ints_sp,
                floats_sp,
                bools_sp
            ),
            cleri_token(CLERI_NONE, """)
        ),
        cleri_sequence(
            CLERI_NONE,
            3,
            cleri_token(CLERI_NONE, "{"),
            cleri_choice(
                CLERI_NONE,
                CLERI_MOST_GREEDY,
                4,
                ints_sp,
                floats_sp,
                bools_sp,
                strings_sp
            ),
            cleri_token(CLERI_NONE, "}")
        )
    );
    cleri_t * one_d_array = cleri_sequence(
        CLERI_GID_ONE_D_ARRAY,
        3,
        cleri_token(CLERI_NONE, "["),
        cleri_choice(
            CLERI_NONE,
            CLERI_MOST_GREEDY,
            4,
            ints,
            floats,
            strings,
            bools
        ),
        cleri_token(CLERI_NONE, "]")
    );
    cleri_t * one_d_arrays = cleri_list(CLERI_GID_ONE_D_ARRAYS, one_d_array, cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * two_d_array = cleri_sequence(
        CLERI_GID_TWO_D_ARRAY,
        3,
        cleri_token(CLERI_NONE, "["),
        one_d_arrays,
        cleri_token(CLERI_NONE, "]")
    );
    cleri_t * key_item = cleri_choice(
        CLERI_GID_KEY_ITEM,
        CLERI_MOST_GREEDY,
        1,
        r_string
    );
    cleri_t * val_item = cleri_choice(
        CLERI_GID_VAL_ITEM,
        CLERI_MOST_GREEDY,
        8,
        r_integer,
        r_float,
        k_true,
        k_false,
        old_one_d_array,
        one_d_array,
        two_d_array,
        r_string
    );
    cleri_t * kv_pair = cleri_sequence(
        CLERI_GID_KV_PAIR,
        4,
        key_item,
        cleri_token(CLERI_NONE, "="),
        val_item,
        cleri_regex(CLERI_NONE, "^\\s*")
    );
    cleri_t * properties_val_str = cleri_regex(CLERI_GID_PROPERTIES_VAL_STR, "^([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+)(:([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+))*");
    cleri_t * properties_kv_pair = cleri_sequence(
        CLERI_GID_PROPERTIES_KV_PAIR,
        4,
        cleri_keyword(CLERI_NONE, "Properties", CLERI_CASE_SENSITIVE),
        cleri_token(CLERI_NONE, "="),
        properties_val_str,
        cleri_regex(CLERI_NONE, "^\\s*")
    );
    cleri_t * old_float_array_9 = cleri_sequence(
        CLERI_GID_OLD_FLOAT_ARRAY_9,
        3,
        cleri_token(CLERI_NONE, """),
        cleri_repeat(CLERI_NONE, r_float, 9, 9),
        cleri_token(CLERI_NONE, """)
    );
    cleri_t * old_float_array_3 = cleri_sequence(
        CLERI_GID_OLD_FLOAT_ARRAY_3,
        3,
        cleri_token(CLERI_NONE, """),
        cleri_repeat(CLERI_NONE, r_float, 3, 3),
        cleri_token(CLERI_NONE, """)
    );
    cleri_t * float_array_3 = cleri_sequence(
        CLERI_GID_FLOAT_ARRAY_3,
        3,
        cleri_token(CLERI_NONE, "["),
        cleri_list(CLERI_NONE, r_float, cleri_token(CLERI_NONE, ","), 3, 3, 0),
        cleri_token(CLERI_NONE, "]")
    );
    cleri_t * float_array_3x3 = cleri_sequence(
        CLERI_GID_FLOAT_ARRAY_3X3,
        3,
        cleri_token(CLERI_NONE, "["),
        cleri_repeat(CLERI_NONE, float_array_3, 3, 3),
        cleri_token(CLERI_NONE, "]")
    );
    cleri_t * lattice_kv_pair = cleri_sequence(
        CLERI_GID_LATTICE_KV_PAIR,
        4,
        cleri_keyword(CLERI_NONE, "Lattice", CLERI_CASE_SENSITIVE),
        cleri_token(CLERI_NONE, "="),
        cleri_choice(
            CLERI_NONE,
            CLERI_MOST_GREEDY,
            4,
            old_float_array_9,
            old_float_array_3,
            float_array_3,
            float_array_3x3
        ),
        cleri_regex(CLERI_NONE, "^\\s*")
    );
    cleri_t * all_kv_pair = cleri_choice(
        CLERI_GID_ALL_KV_PAIR,
        CLERI_FIRST_MATCH,
        3,
        properties_kv_pair,
        lattice_kv_pair,
        kv_pair
    );
    cleri_t * START = cleri_repeat(CLERI_GID_START, all_kv_pair, 0, 0);

    cleri_grammar_t * grammar = cleri_grammar(START, "^\\w+");

    return grammar;
}
