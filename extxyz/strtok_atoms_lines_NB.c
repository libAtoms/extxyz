#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *get_token(char **l) {
    char *token;

    if (**l == '"') {
        // deal with quotes
        token = strtok(*l, "\"");
    } else {
        token = strtok(*l, " \t");
    }
    // skip to next token
    *l += (token-*l) + strlen(token)+1;

    return token;
}

int main(int argc, char *argv[]) {
    char *l = (char *) malloc(1024*sizeof(char));

    int n_fields = 10;
    char prop_fmts[10];

    int v_i;
    double v_f;
    int v_l;
    char v_s[1024];

    prop_fmts[0] = 'S';
    prop_fmts[1] = 'R';
    prop_fmts[2] = 'R';
    prop_fmts[3] = 'R';
    prop_fmts[4] = 'R';
    prop_fmts[5] = 'R';
    prop_fmts[6] = 'R';
    prop_fmts[7] = 'I';
    prop_fmts[8] = 'L';
    prop_fmts[9] = 'S';

    while (fgets(l, 1023, stdin)) {
        for (int field_i=0; field_i < n_fields; field_i++) {
            int n_parsed;

            char *token = get_token(&l);
            if (!token) {
                fprintf(stderr, "Failed to get token from l '%s'\n", l);
                exit(1);
            }

            if (prop_fmts[field_i] == 'I') {
                n_parsed = sscanf(token, "%d", &v_i);
                printf("int %d\n", v_i);
            } else if (prop_fmts[field_i] == 'R') {
                n_parsed = sscanf(token, "%lf", &v_f);
                printf("float %f\n", v_f);
            } else if (prop_fmts[field_i] == 'L') {
                n_parsed = sscanf(token, "%s", v_s);
                if (strlen(v_s) != 1) {
                    fprintf(stderr, "invalid value for bool '%s'\n", v_s);
                    exit(1);
                }
                if (v_s[0] == 'T') {
                    v_l = 1;
                    n_parsed = 1;
                } else if (v_s[0] == 'F') {
                    v_l = 0;
                    n_parsed = 1;
                } else {
                    n_parsed = 0;
                }
                printf("logical %d\n", v_l);
            } else if (prop_fmts[field_i] == 'S') {
                n_parsed = sscanf(token, "%s", &v_s);
                printf("string %s\n", v_s);
            } else {
                fprintf(stderr, "Unknown properties format %c for field %d\n", prop_fmts[field_i], field_i);
                exit(2);
            }
            if (n_parsed != 1) {
                fprintf(stderr, "Failed to parse field %d format %s from '%s'\n", field_i, prop_fmts[field_i], token);
                exit(2);
            }
        }
    }
}
