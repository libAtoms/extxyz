/*
 * extxyz_kv_grammar.c
 *
 * This grammar is generated using the Grammar.export_c() method and
 * should be used with the libcleri module.
 *
 * Source class: ExtxyzKVGrammar
 * Created at: 2021-02-18 15:00:29
 */

#include "extxyz_kv_grammar.h"
#include <stdio.h>

#define CLERI_CASE_SENSITIVE 0
#define CLERI_CASE_INSENSITIVE 1

#define CLERI_FIRST_MATCH 0
#define CLERI_MOST_GREEDY 1

cleri_grammar_t * compile_extxyz_kv_grammar(void)
{
    cleri_t * r_barestring = cleri_regex(CLERI_GID_R_BARESTRING, "^(?:[^\\s=\",}{\\]\\[\\\\]|(?:\\\\[\\s=\",}{\\]\\[\\\\]))+");
    cleri_t * r_dq_quotedstring = cleri_regex(CLERI_GID_R_DQ_QUOTEDSTRING, "^(\")(?:(?=(\\\\?))\\2.)*?\\1");
    cleri_t * r_cb_quotedstring = cleri_regex(CLERI_GID_R_CB_QUOTEDSTRING, "^{(?:[^{}]|\\\\[{}])*(?<!\\\\)}");
    cleri_t * r_sb_quotedstring = cleri_regex(CLERI_GID_R_SB_QUOTEDSTRING, "^\\[(?:[^\\[\\]]|\\\\[\\[\\]])*(?<!\\\\)\\]");
    cleri_t * r_string = cleri_choice(
        CLERI_GID_R_STRING,
        CLERI_MOST_GREEDY,
        4,
        r_barestring,
        r_dq_quotedstring,
        r_cb_quotedstring,
        r_sb_quotedstring
    );
    cleri_t * r_integer = cleri_regex(CLERI_GID_R_INTEGER, "^[+-]?(?:0|[1-9][0-9]*)\\b");
    cleri_t * r_float = cleri_regex(CLERI_GID_R_FLOAT, "^[+-]?(?:(?:(?:0|[1-9][0-9]*)\\.|\\.)[0-9]*(?:[dDeE][+-]?[0-9]+)?|(?:0|[1-9][0-9]*)(?:[dDeE][+-]?[0-9]+)?|(?:0|[1-9][0-9]*))(?:\\b|(?=\\W)|$)");
    cleri_t * r_true = cleri_regex(CLERI_GID_R_TRUE, "^\\b(?:[tT]rue|TRUE|T)\\b");
    cleri_t * r_false = cleri_regex(CLERI_GID_R_FALSE, "^\\b(?:[fF]alse|FALSE|F)\\b");
    cleri_t * ints = cleri_list(CLERI_GID_INTS, r_integer, cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * floats = cleri_list(CLERI_GID_FLOATS, r_float, cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * bools = cleri_list(CLERI_GID_BOOLS, cleri_choice(
        CLERI_NONE,
        CLERI_MOST_GREEDY,
        2,
        r_true,
        r_false
    ), cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * strings = cleri_list(CLERI_GID_STRINGS, r_string, cleri_token(CLERI_NONE, ","), 1, 0, 0);
    cleri_t * ints_sp = cleri_repeat(CLERI_GID_INTS_SP, r_integer, 1, 0);
    cleri_t * floats_sp = cleri_repeat(CLERI_GID_FLOATS_SP, r_float, 1, 0);
    cleri_t * bools_sp = cleri_repeat(CLERI_GID_BOOLS_SP, cleri_choice(
        CLERI_NONE,
        CLERI_MOST_GREEDY,
        2,
        r_true,
        r_false
    ), 1, 0);
    cleri_t * strings_sp = cleri_repeat(CLERI_GID_STRINGS_SP, r_string, 1, 0);
    cleri_t * old_one_d_array = cleri_choice(
        CLERI_GID_OLD_ONE_D_ARRAY,
        CLERI_MOST_GREEDY,
        2,
        cleri_sequence(
            CLERI_NONE,
            3,
            cleri_token(CLERI_NONE, "\""),
            cleri_choice(
                CLERI_NONE,
                CLERI_MOST_GREEDY,
                6,
                ints_sp,
                ints,
                floats_sp,
                floats,
                bools_sp,
                bools
            ),
            cleri_token(CLERI_NONE, "\"")
        ),
        cleri_sequence(
            CLERI_NONE,
            3,
            cleri_token(CLERI_NONE, "{"),
            cleri_choice(
                CLERI_NONE,
                CLERI_MOST_GREEDY,
                8,
                ints_sp,
                ints,
                floats_sp,
                floats,
                bools_sp,
                bools,
                strings_sp,
                strings
            ),
            cleri_token(CLERI_NONE, "}")
        )
    );
    cleri_t * one_d_array_i = cleri_sequence(
        CLERI_GID_ONE_D_ARRAY_I,
        3,
        cleri_token(CLERI_NONE, "["),
        ints,
        cleri_token(CLERI_NONE, "]")
    );
    cleri_t * one_d_array_f = cleri_sequence(
        CLERI_GID_ONE_D_ARRAY_F,
        3,
        cleri_token(CLERI_NONE, "["),
        floats,
        cleri_token(CLERI_NONE, "]")
    );
    cleri_t * one_d_array_b = cleri_sequence(
        CLERI_GID_ONE_D_ARRAY_B,
        3,
        cleri_token(CLERI_NONE, "["),
        bools,
        cleri_token(CLERI_NONE, "]")
    );
    cleri_t * one_d_array_s = cleri_sequence(
        CLERI_GID_ONE_D_ARRAY_S,
        3,
        cleri_token(CLERI_NONE, "["),
        strings,
        cleri_token(CLERI_NONE, "]")
    );
    cleri_t * one_d_arrays = cleri_choice(
        CLERI_GID_ONE_D_ARRAYS,
        CLERI_MOST_GREEDY,
        4,
        cleri_list(CLERI_NONE, one_d_array_i, cleri_token(CLERI_NONE, ","), 1, 0, 0),
        cleri_list(CLERI_NONE, one_d_array_f, cleri_token(CLERI_NONE, ","), 1, 0, 0),
        cleri_list(CLERI_NONE, one_d_array_b, cleri_token(CLERI_NONE, ","), 1, 0, 0),
        cleri_list(CLERI_NONE, one_d_array_s, cleri_token(CLERI_NONE, ","), 1, 0, 0)
    );
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
        11,
        r_integer,
        r_float,
        r_true,
        r_false,
        two_d_array,
        old_one_d_array,
        one_d_array_i,
        one_d_array_f,
        one_d_array_b,
        one_d_array_s,
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
    cleri_t * properties = cleri_keyword(CLERI_GID_PROPERTIES, "Properties", CLERI_CASE_INSENSITIVE);
    cleri_t * properties_val_str = cleri_regex(CLERI_GID_PROPERTIES_VAL_STR, "^([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+)(:([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+))*");
    cleri_t * properties_kv_pair = cleri_sequence(
        CLERI_GID_PROPERTIES_KV_PAIR,
        4,
        properties,
        cleri_token(CLERI_NONE, "="),
        properties_val_str,
        cleri_regex(CLERI_NONE, "^\\s*")
    );
    cleri_t * all_kv_pair = cleri_choice(
        CLERI_GID_ALL_KV_PAIR,
        CLERI_FIRST_MATCH,
        2,
        properties_kv_pair,
        kv_pair
    );
    cleri_t * START = cleri_repeat(CLERI_GID_START, all_kv_pair, 0, 0);

    cleri_grammar_t * grammar = cleri_grammar(START, "^\\w+");

    return grammar;
}
