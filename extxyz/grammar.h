/*
 * grammar.h
 *
 * This grammar is generated using the Grammar.export_c() method and
 * should be used with the libcleri module.
 *
 * Source class: ExtxyzKVGrammar
 * Created at: 2020-11-27 14:56:41
 */
#ifndef CLERI_EXPORT_GRAMMAR_H_
#define CLERI_EXPORT_GRAMMAR_H_

#include <cleri/cleri.h>

cleri_grammar_t * compile_grammar(void);

enum cleri_grammar_ids {
    CLERI_NONE,   // used for objects with no name
    CLERI_GID_ALL_KV_PAIR,
    CLERI_GID_BOOLS,
    CLERI_GID_BOOLS_SP,
    CLERI_GID_FLOATS,
    CLERI_GID_FLOATS_SP,
    CLERI_GID_FLOAT_ARRAY_3,
    CLERI_GID_FLOAT_ARRAY_3X3,
    CLERI_GID_INTS,
    CLERI_GID_INTS_SP,
    CLERI_GID_KEY_ITEM,
    CLERI_GID_KV_PAIR,
    CLERI_GID_K_FALSE,
    CLERI_GID_K_TRUE,
    CLERI_GID_LATTICE_KV_PAIR,
    CLERI_GID_OLD_FLOAT_ARRAY_3,
    CLERI_GID_OLD_FLOAT_ARRAY_9,
    CLERI_GID_OLD_ONE_D_ARRAY,
    CLERI_GID_ONE_D_ARRAY,
    CLERI_GID_ONE_D_ARRAYS,
    CLERI_GID_PROPERTIES_KV_PAIR,
    CLERI_GID_PROPERTIES_VAL_STR,
    CLERI_GID_R_BARESTRING,
    CLERI_GID_R_FLOAT,
    CLERI_GID_R_INTEGER,
    CLERI_GID_R_QUOTEDSTRING,
    CLERI_GID_R_STRING,
    CLERI_GID_START,
    CLERI_GID_STRINGS,
    CLERI_GID_STRINGS_SP,
    CLERI_GID_TWO_D_ARRAY,
    CLERI_GID_VAL_ITEM,
    CLERI_END // can be used to get the enum length
};

#endif /* CLERI_EXPORT_GRAMMAR_H_ */

