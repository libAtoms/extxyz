#include <stdio.h>
#include <cleri/cleri.h>
#include "grammar.h"

void test_str(cleri_grammar_t * grammar, const char * str)
{
    cleri_parse_t * pr = cleri_parse(grammar, str);
    printf("Test string '%s': %s\n", str, pr->is_valid ? "true" : "false");
    cleri_parse_free(pr);
}

int main(void)
{
    /* compile grammar */
    cleri_grammar_t * my_grammar = compile_grammar();

    /* test some strings */
    test_str(my_grammar, "hi \"Iris\"");  // true
    test_str(my_grammar, "bye \"Iris\""); // false

    /* cleanup grammar */
    cleri_grammar_free(my_grammar);

    return 0;
}
