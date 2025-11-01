/*
 * grammar.h
 *
 * This grammar is generated using the Grammar.export_c() method and
 * should be used with the libcleri module.
 *
 * Source class: MyGrammar
 * Created at: 2020-10-30 14:47:45
 */
#ifndef CLERI_EXPORT_GRAMMAR_H_
#define CLERI_EXPORT_GRAMMAR_H_

#include <cleri/cleri.h>

cleri_grammar_t * compile_grammar(void);

enum cleri_grammar_ids {
    CLERI_NONE,   // used for objects with no name
    CLERI_GID_K_HI,
    CLERI_GID_R_NAME,
    CLERI_GID_START,
    CLERI_END // can be used to get the enum length
};

#endif /* CLERI_EXPORT_GRAMMAR_H_ */

