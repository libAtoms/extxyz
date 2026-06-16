/* First-char-dispatch parser for the extended-XYZ comment line.
 *
 * A hand-written, grammar-faithful alternative to the libcleri grammar walk
 * (cleri_parse + tree_to_dict): it dispatches each value on its first non-space
 * character so only the relevant val_item alternative(s) are tried, and folds
 * parse + marshalling into a single pass. It accepts EXACTLY the same language
 * as the pyleri/libcleri grammar and produces a byte-identical DictEntry list;
 * provability is maintained by a differential conformance test against cleri
 * (tests/test_dispatch_parity.py), with cleri retained as the canonical grammar.
 *
 * Selected at read time by use_cleri=0 (see extxyz_read_ll_opts). Reuses the
 * grammar's own PCRE2 token patterns (INTEGER_RE/FLOAT_RE/BOOL_RE/...), so the
 * accepted token language is identical by construction.
 */
#ifndef EXTXYZ_DISPATCH_H
#define EXTXYZ_DISPATCH_H

struct dict_entry_struct;

/* Compile + JIT the token regexes once. Idempotent; safe to call repeatedly.
 * Called eagerly at Python import and lazily on first parse otherwise. */
void extxyz_dispatch_init(void);

/* Free the cached compiled regexes (process-exit cleanup, mirrors the grammar
 * free); leaves the parser re-initialisable. */
void extxyz_dispatch_free(void);

/* Parse comment line `s`. Returns a DictEntry linked list identical to
 * tree_to_dict(), or NULL on a parse error (with `error_message`, if non-NULL,
 * set to a "Failed to parse string ..." message matching the cleri path). */
struct dict_entry_struct *extxyz_dispatch_parse(const char *s, char *error_message);

#endif /* EXTXYZ_DISPATCH_H */
