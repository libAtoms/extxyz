#include <stdio.h>
#include <stdlib.h>

int is_whitespace(char c) {
    return (c == ' ' || c == '\t');
}
int is_EOL(char c) {
    return ((int)c == 0 || (int)c == 10 || (int)c == 13);
}

char *get_token(char **line, int *error) {
    char *token_start, *token_c;

    *error = 0;
    /* check for EOL */
    if (is_EOL((*line)[0])) {
        return 0;
    }

    /* strip initial whitespace */
    while (is_whitespace((*line)[0])) {
        (*line)++;
        if (is_EOL((*line)[0])) {
            return 0;
        }
    }

    int in_quotes = 0;
    int first_char = 1;
    token_start = *line;
    token_c = token_start;
    while (in_quotes || ! is_whitespace((*line)[0])) {
        // printf("loop start cur char '%c' %d\n", (*line)[0], (int)((*line)[0]));
        if (is_EOL((*line)[0])) {
            // printf("is_eol\n");
            if (in_quotes) {
                /* line ended mid quote */
                *error = 1;
                return 0;
            }
            break;
        }

        if ((*line)[0] == '"') {
            /* toggle state */
            in_quotes = ! in_quotes;
            /* skip the actual quote character */
            (*line)++;
            if (first_char) {
                token_start = *line;
                token_c = token_start;
            }
            /* this may be the end of the token, go back to start of loop 
               to check for whitespace, EOL, etc */
            continue;
        }
        /* now on a real character */
        if ((*line)[0] == '\\') {
            /* skip, will treat next below as literal */
            (*line)++;
            if (is_EOL((*line)[0])) {
                *error = 2;
                return 0;
            }
        }

        // printf("copying char '%c' %d\n", (*line)[0], (int)((*line)[0]));
        /* copy character, increment place in line and place in token */
        *token_c = (*line[0]);
        token_c++;
        (*line)++;

        first_char = 0;
    }
    // printf("returning, end of token '%c' %d\n", (*line)[0], (int)((*line)[0]));
    // printf("token '%s'\n", token_start);
    /* after final character, make sure token is null terminated */
    *token_c = 0;
    (*line)++;
    return token_start;
}

int main (int argc, char *argv[]) {
    char *line, *token;
    int err;

    line = (char *) malloc(500 * sizeof(char));

    fgets(line, 499, stdin);
    while (token = get_token(&line, &err)) {
        printf("got token '%s'\n", token);
        if (! line[0]) {
            break;
        }
    }
    if (err != 0) {
        printf("got err %d\n", err);
    }
}
