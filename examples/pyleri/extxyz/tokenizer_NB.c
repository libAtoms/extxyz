#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int is_whitespace(char c) {
    return (c == ' ' || c == '\t');
}
int is_EOL(char c) {
    return ((int)c == 0 || (int)c == 10 || (int)c == 13);
}

#define STAT_SPECIAL_TOKEN -1
#define STAT_NORMAL 0
#define STAT_EOL 1
#define STAT_ERR_MID_QUOTE 2
#define STAT_ERR_BACKSLASH 3

int get_token(char **line, char *token) {
    char *token_c;
    // printf("STARTING tokenizing '%s'\n", *line);

    int status = 0;
    /* check for EOL */
    if (is_EOL((*line)[0])) {
        return STAT_EOL;
    }

    /* strip initial whitespace */
    while (is_whitespace((*line)[0])) {
        (*line)++;
        if (is_EOL((*line)[0])) {
            return STAT_EOL;
        }
    }

    // printf("post whitespace '%s'\n", *line);

    int in_quotes = 0;
    token_c = token;
    while (in_quotes || ! is_whitespace((*line)[0])) {
        // printf("loop start cur char '%c'\n", (*line)[0]);
        if (is_EOL((*line)[0])) {
            // printf("is_eol\n");
            if (in_quotes) {
                /* line ended mid quote */
                return STAT_ERR_MID_QUOTE;
            }
            break;
        }

        if (! in_quotes) {
            /* look for special tokens */
            char cur_char = (*line)[0];
            // printf("check cur '%c' for special\n", cur_char);
            if (cur_char == '[' || cur_char == ']' || cur_char == '{' || cur_char == '}' || cur_char == '=' || cur_char == ',') {
                // printf("looks special, is '%c'\n", (*line)[0]);
                /* this char is a special token */
                token[0] = (*line)[0];
                token[1] = 0;
                (*line)++;
                // printf("returning from special %c with line '%s'\n", token[0], (*line));
                return STAT_SPECIAL_TOKEN;
            }
            char next_char = (*line)[1];
            // printf("check next '%c' for special\n", next_char);
            if (cur_char != '\\' && (next_char == '[' || next_char == ']' || next_char == '{' || next_char == '}' || next_char == '=' || next_char == ',')) {
                // printf("next looks special, end now\n");
                /* next char is special, end this token now */
                /* copy and null terminate */
                *token_c = (*line)[0];
                token_c++;
                *token_c = 0;
                /* advance line */
                (*line)++;
                return STAT_NORMAL;
            }
        }

        if ((*line)[0] == '"') {
            /* toggle state */
            in_quotes = ! in_quotes;
            /* skip the actual quote character */
            (*line)++;
            /* this may be the end of the token, go back to start of loop 
               to check for whitespace, EOL, etc */
            if (!in_quotes) {
                char cur_char = (*line)[0];
                if (cur_char == '[' || cur_char == ']' || cur_char == '{' || cur_char == '}' || cur_char == '=' || cur_char == ',') {
                    // printf("cur after quotes looks special, end now\n");
                    /* cur char is special, end this token now */
                    /* null terminate */
                    token_c++;
                    *token_c = 0;
                    return STAT_NORMAL;
                }
            }
            continue;
        }

        /* now on a real character */
        if ((*line)[0] == '\\') {
            /* skip, will treat next below as literal */
            (*line)++;
            // printf("post backslash, *line[0] %c\n", (*line)[0]);
            if (is_EOL((*line)[0])) {
                return STAT_ERR_BACKSLASH;
            }
        }

        // printf("copying char '%c' %d\n", (*line)[0], (int)((*line)[0]));
        /* copy character, increment place in line and place in token */
        *token_c = (*line[0]);
        token_c++;
        (*line)++;
    }
    // printf("returning, end of token '%c' %d\n", (*line)[0], (int)((*line)[0]));
    // printf("token '%s'\n", token_start);
    /* after final character, make sure token is null terminated */
    *token_c = 0;
    (*line)++;
    return STAT_NORMAL;
}

#define TYPE_UNSET 0
#define TYPE_I 1
#define TYPE_F 2
#define TYPE_L 3
#define TYPE_S 4

typedef struct val_item {
    int i;
    double f;
    int l;
    char *s;
    int type;
} val_s;

typedef struct val_list_item {
    val_s *v;
    struct val_list_item *next;
} val_list_s;


val_s *new_val_s() {
    val_s *v;
    v = (val_s *) malloc(sizeof(val_s));
    v->type = TYPE_UNSET;
    v->s = 0;
    return v;
}

void free_val_s(val_s **v) {
    if ((*v)->s) {
        free ((*v)->s);
    }
    free(*v);
    *v = 0;
}

void print_val_s(val_s v) {
    if (v.type == TYPE_I) {
        printf("I %d", v.i);
    } else if (v.type == TYPE_F) {
        printf("F %f", v.f);
    } else if (v.type == TYPE_L) {
        printf("B %c", v.l ? 'T' : 'F');
    } else if (v.type == TYPE_S) {
        printf("S %s", v.s);
    } else {
        printf("UNKNOWN");
    }
}

void parse_prim(const char *s, val_s *v) {
    if (s[0] == 'T' && s[1] == 0) {
        v->type = TYPE_L;
        v->l = 1;
    } else if (s[0] == 'F' && s[1] == 0) {
        v->type = TYPE_L;
        v->l = 0;
    } else if (sscanf(s, "%d", &(v->i)) == 1) {
        v->type = TYPE_I;
    } else if (sscanf(s, "%lf", &(v->f)) == 1) {
        v->type = TYPE_F;
    } else {
        v->s = (char *) malloc (strlen(s) * sizeof(char));
        strcpy(v->s, s);
        v->type = TYPE_S;
    }
}

int main (int argc, char *argv[]) {
    char *line, *key_token, *eq_token, *val_token;
    int stat;
    val_s *val;
    char array_open, array_close;
    val_list_s *head, *cur;

    line = (char *) malloc(500 * sizeof(char));
    key_token = (char *) malloc(500 * sizeof(char));
    eq_token = (char *) malloc(500 * sizeof(char));
    val_token = (char *) malloc(500 * sizeof(char));

    cur = head = 0;

    fgets(line, 499, stdin);

    while (1) {
        head = 0;
        stat = get_token(&line, key_token);
        if (stat == STAT_EOL) {
            printf("EOL\n");
            break;
        }
        if (stat != 0) {
            printf("ERROR: token is special or error looking for key %d '%s'\n", stat, key_token);
            exit(1);
        }

        stat = get_token(&line, eq_token);
        if (stat != STAT_SPECIAL_TOKEN || eq_token[0] != '=') {
            printf("ERROR: token is regular, missing or wrong special looking for '=' %d '%s'\n", stat, eq_token);
            exit(1);
        }

        int depth = 0;
        int array_cols = -1;
        int cur_array_col = -1;
        int cur_array_row = -1;
        int ok_pre_comma = 0;
        while ((stat = get_token(&line, val_token)) <= 0) {
            // printf("got token '%s' now line '%s'\n", val_token, line);
            if (stat > 0) {
                printf("ERROR while getting value token\n");
                exit(1);
            }
            if (stat == 0) {
                // printf("primitive token\n");
                /* primitive token */
                val = new_val_s();
                parse_prim(val_token, val);
                if (depth == 0) {
                    // printf("outside array, ending\n");
                    /* just a scalar */
                    break;
                }
            }
            /* now should be special token only */

            if (val_token[0] == ',') {
                if (! ok_pre_comma) {
                    printf("ERROR: comma after something other than prim or array close\n");
                    exit(1);
                }
                // printf("got an OK comma, skipping rest\n");
                ok_pre_comma = 0;
                continue;
            }
            /* this character not OK pre comma by default */
            ok_pre_comma = 0;

            if (strchr("[{", val_token[0])) {
                // printf("got an array open\n");
                if (depth == 0) {
                    // printf("initial array \n");
                    array_open = val_token[0];
                    array_close = (array_open == '[') ? ']' : '}';
                    cur_array_row = 0;
                } else {
                    // printf("deeper array \n");
                    if (val_token[0] != array_open) {
                        printf("ERROR: mix of array symbols in array\n");
                        exit(1);
                    }
                }
                cur_array_col = 0;
                depth++;
                if (depth > 2) {
                    printf("ERROR: array too deep\n");
                    exit(1);
                }
                continue;
            }
            if (strchr("]}", val_token[0])) {
                // printf("array close \n");
                /* array close is OK pre comma */
                ok_pre_comma = 1;
                if (val_token[0] != array_close) {
                    printf("ERROR: mix of array symbols in array\n");
                    exit(1);
                }
                if (cur_array_col == 0) {
                    printf("ERROR: empty array\n");
                    exit(1);
                }
                if (depth == 2) {
                    /* closing a nested row */
                    if (cur_array_row == 0) {
                        /* record number of columns */
                        array_cols = cur_array_col;
                    } else if (cur_array_col != array_cols) {
                        printf("ERROR mismatched number of cols in array row\n");
                        exit(1);
                    }
                }
                depth--;
                if (depth == 0) {
                    // printf("overall end of array\n");
                    /* end of array */
                    if ( ! is_whitespace(line[0]) && ! is_EOL(line[0])) {
                        printf("ERROR: end of array not followed by whitespace or EOL '%c'\n", line[0]);
                        exit(1);
                    }
                    break;
                }
                /* successful open */
                cur_array_row++;
                continue;
            }

            cur_array_col++;
            /* prim token, OK pre comma */
            ok_pre_comma = 1;
            if (!head) {
                head = (val_list_s *) malloc(sizeof(val_list_s));
                cur = head;
            } else {
                val_list_s *new = (val_list_s *) malloc(sizeof(val_list_s));
                cur->next = new;
                cur = new;
            }
            // // printf("cur %d\n", cur);
            cur->v = new_val_s();
            cur->next = 0;
            // printf("parsing '%s'\n", val_token);
            parse_prim(val_token, cur->v);
        }

        printf("got key '%s'\n", key_token);
        printf("got value '");
        if (head) {
            /* array of some sort */
            val_list_s *v;

            int item_type;
            int int_to_float = 0;
            for (v = head, item_type = v->v->type; v; v = v->next) {
                if (v->v->type != item_type) {
                    if ((item_type == TYPE_I && v->v->type == TYPE_F) ||
                        (item_type == TYPE_F && v->v->type == TYPE_I)) {
                        int_to_float = 1;
                    } else {
                        printf("ERROR mismatched types in array\n");
                        exit(1);
                    }
                }
            }
            if (int_to_float) {
                for (v = head; v; v = v->next) {
                    if (v->v->type != TYPE_F) {
                        v->v->type = TYPE_F;
                        v->v->f = v->v->i;
                    }
                }
            }

            int item_i;
            for (v = head, item_i = 0; v; v = v->next, item_i++) {
                print_val_s(*(v->v));
                free_val_s(&(v->v));
                if (v->next) {
                    if (cur_array_row > 1 && item_i % cur_array_col == cur_array_col-1) {
                        printf("\n           ");
                    } else {
                        printf(" ");
                    }
                }
            }
            v = head;
            while (v) {
                val_list_s *next = v->next;
                free(v);
                v = next;
            }
        } else {
            print_val_s(*val);
            free_val_s(&val);
        }
        printf("'\n\n");
    }

    if (stat != STAT_EOL) {
        printf("got error stat %d\n", stat);
        exit(stat);
    }
}
