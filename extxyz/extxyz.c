#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cleri/cleri.h>
#include "extxyz_kv_grammar.h"

enum data_type {data_i, data_f, data_b, data_s};

typedef struct data_list_struct {
    union {
        int i;
        double f;
        char *s;
        int b;
    } data;

    struct data_list_struct *next;
} DataList;

typedef struct arrays_struct {
    char *key;

    union {
        int *i;
        double *f;
        char **s;
        int *b;
    } data;

    enum data_type data_t;
    int nrows, ncols;

    struct arrays_struct *next;
} Arrays;

typedef struct dict_entry_struct {
    char *key;

    DataList *first_data, *last_data;
    enum data_type data_t; 
    int nrows, ncols, n_in_row;

    struct dict_entry_struct *next;
} DictEntry;

int parse_tree(cleri_node_t *node, DictEntry **cur_entry, int *in_seq, int *in_entry) {
    //DEBUG printf("enter parse_tree in_entry %d\n", *in_entry);
    //DEBUG if (node->cl_obj) {
        //DEBUG printf("node type %d gid %d", node->cl_obj->tp, node->cl_obj->gid);
        //DEBUG if (1) { // node->cl_obj->tp == CLERI_TP_KEYWORD || node->cl_obj->tp == CLERI_TP_REGEX) {
            //DEBUG char *str = (char *) malloc((node->len+1) * sizeof(char));
            //DEBUG strncpy(str, node->str, node->len);
            //DEBUG str[node->len] = 0;
//DEBUG 
            //DEBUG printf(" %s", str);
//DEBUG 
            //DEBUG free(str);
        //DEBUG }
        //DEBUG printf("\n");
    //DEBUG }

    if (*in_entry) {
        //DEBUG printf("in entry, looking for data\n");
        // have key, looking for data
        if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_SEQUENCE)) {
            (*in_seq)++;
            //DEBUG printf("sequence, new in_seq %d\n", *in_seq);
        } else if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_KEYWORD ||
                                    node->cl_obj->tp == CLERI_TP_REGEX)) {
            //DEBUG printf("FOUND keyword or regex\n");
            DataList *new_data = (DataList *) malloc(sizeof(DataList));
            if (! (*cur_entry)->first_data) {
                // no data here yet
                (*cur_entry)->first_data = new_data;
            } else {
                // extend datalist
                (*cur_entry)->last_data->next = new_data;
            }
            (*cur_entry)->last_data = new_data;
            new_data->next = 0;
            (*cur_entry)->n_in_row++;

            if (node->cl_obj->tp == CLERI_TP_REGEX) {
                char * str = (char *) malloc((node->len+1)*sizeof(char));
                strncpy(str, node->str, node->len);
                str[node->len] = 0;

                if (node->cl_obj->gid == CLERI_GID_R_INTEGER) {
                    //DEBUG printf("FOUND int\n");
                    new_data->data.i = atoi(str);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    (*cur_entry)->data_t = data_i;
                    free(str);
                } else if (node->cl_obj->gid == CLERI_GID_R_FLOAT) {
                    //DEBUG printf("FOUND float\n");
                    new_data->data.f = atof(str);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    (*cur_entry)->data_t = data_f;
                    free(str);
                } else if (node->cl_obj->gid == CLERI_GID_R_STRING || 
                           node->cl_obj->gid == CLERI_GID_R_BARESTRING || 
                           node->cl_obj->gid == CLERI_GID_R_QUOTEDSTRING ||
                           node->cl_obj->gid == CLERI_GID_PROPERTIES_VAL_STR) {
                    // is it bad to just use CLERI_GID_PROPERTIES_VAL_STR as though it's a plain string?
                    //DEBUG printf("FOUND string\n");
                    new_data->data.s = str;
                    (*cur_entry)->data_t = data_s;
                } else {
                    // ignore blank regex, they show up sometimes e.g. after end of sequence
                    if (strlen(str) > 0) {
                        fprintf(stderr, "Failed to parse some regex as data key '%s' str '%s'\n", 
                                (*cur_entry)->key, str);
                        free(str);
                        return 1;
                    }
                }
            } else {
                // keyword
                if (node->cl_obj->gid == CLERI_GID_K_TRUE || node->cl_obj->gid == CLERI_GID_K_FALSE) {
                    //DEBUG printf("FOUND keyword bool\n");
                    new_data->data.b = (node->cl_obj->gid == CLERI_GID_K_TRUE);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    (*cur_entry)->data_t = data_b;
                } else {
                    fprintf(stderr, "Failed to parse some keyword as data key '%s'\n", (*cur_entry)->key);
                    return 1;
                }
            }

            if (*in_seq == 0) {
                //DEBUG printf("got scalar, setting in_entry=0\n");
                *in_entry = 0;
            }
        }
    } else {
        //DEBUG printf("looking for key\n");
        // looking for key
        if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_KEYWORD ||
                             node->cl_obj->tp == CLERI_TP_REGEX)) {
            if (node->len == 0) {
                // empty string, skip
                return 0;
            }
            //DEBUG printf("got key, setting in_entry=1\n");
            *in_entry = 1;
            //DEBUG printf("FOUND keyword or regex\n");
            // found something that can contain key
            if ((*cur_entry)->key) {
                // extend linked list
                DictEntry *new_entry = (DictEntry *) malloc(sizeof(DictEntry));
                (*cur_entry)->next = new_entry;
                (*cur_entry) = new_entry;
            }
            // set key
            (*cur_entry)->key = (char *) malloc((node->len+1)*sizeof(char));
            strncpy((*cur_entry)->key, node->str, node->len);
            (*cur_entry)->key[node->len] = 0;
            // zero other things
            (*cur_entry)->first_data = (*cur_entry)->last_data = 0;
            (*cur_entry)->nrows = (*cur_entry)->ncols = (*cur_entry)-> n_in_row = 0;
            (*cur_entry)->next = 0;
            //DEBUG printf("got key '%s'\n", (*cur_entry)->key);
            // key containing objects never have children
            return 0;
        }
    }

    //DEBUG printf("looping over children\n");
    for (cleri_children_t *child = node->children; child; child = child->next) {
        //DEBUG printf("child\n");
        int err = parse_tree(child->node, cur_entry, in_seq, in_entry);
        if (err) {
            return err;
        }
    }

    if (node->cl_obj && node->cl_obj->tp == CLERI_TP_SEQUENCE) {
        //DEBUG printf("leaving sequence\n");
        if (*in_seq == 2) {
            //DEBUG printf("leaving inner row\n");
            // leaving a row in a nested list
            if ((*cur_entry)->ncols > 0 && (*cur_entry)->ncols != (*cur_entry)->n_in_row) {
                // not first row
                fprintf(stderr, "key %s number of entries per row %d inconsistent with prev %d\n", 
                        (*cur_entry)->key, (*cur_entry)->ncols, (*cur_entry)->n_in_row);
                return 1;
            }
            (*cur_entry)->nrows++;
            (*cur_entry)->ncols = (*cur_entry)->n_in_row;
            (*cur_entry)->n_in_row = 0;
            // exiting sequence
            (*in_seq)--;
        } else if (*in_seq == 1) {
            //DEBUG printf("leaving outer row\n");
            if ((*cur_entry)->ncols == 0) {
                (*cur_entry)->ncols = (*cur_entry)->n_in_row;
                (*cur_entry)->n_in_row = 0;
            }
            // exiting sequence
            (*in_seq)--;
            //DEBUG printf("exiting top level sequence, setting in_entry=0\n");
            *in_entry = 0;
        }
    }

    //DEBUG printf("leaving parse\n");
    return 0;
}

void dump_tree(cleri_node_t *node, char *prefix) {
    char *new_prefix = (char *) malloc((strlen(prefix) + 3)* sizeof(char));
    new_prefix[0] = 0;
    strcat(new_prefix, prefix);
    strcat(new_prefix, "  ");

    if (node->cl_obj) {
        printf("%snode type %d gid %d", prefix, node->cl_obj->tp, node->cl_obj->gid);
        if (1) { // node->cl_obj->tp == CLERI_TP_KEYWORD || node->cl_obj->tp == CLERI_TP_REGEX)
            char *str = (char *) malloc((node->len+1) * sizeof(char));
            strncpy(str, node->str, node->len);
            str[node->len] = 0;

            printf(" %s", str);

            free(str);
        }
        printf("\n");
    } else {
        printf("%snode\n", prefix, node->cl_obj);
    }

    for (cleri_children_t *child = node->children; child; child = child->next) {
        dump_tree(child->node, new_prefix);
    }

    free(new_prefix);
}

void *tree_to_dict(cleri_parse_t *tree) {
    if (! tree->is_valid) {
        fprintf(stderr, "Failed to parse string at pos %d\n", tree->pos);
        return 0;
    }

    // dump_tree(tree->tree, "");
    // printf("END DUMP\n");

    DictEntry *dict = (DictEntry *) malloc(sizeof(DictEntry));
    dict->key = 0;
    dict->first_data = dict->last_data = 0;
    dict->next = 0;

    DictEntry *cur_entry = dict;

    int in_seq = 0, in_entry = 0;
    int err = parse_tree(tree->tree, &cur_entry, &in_seq, &in_entry);
    if (err) {
        fprintf(stderr, "error parsing tree\n");
        exit(1);
    }

    return dict;
}


int extxyz_read(cleri_grammar_t *kv_grammar, FILE *fp, DictEntry **info, Arrays **arrays) {
    int nat;
    char line[10240];

    char *stat = fgets(line, 10239, fp);
    if (! stat) {
        return 0;
    }
    sscanf(line, "%d", &nat);

    fgets(line, 10239, fp);
    cleri_parse_t * tree = cleri_parse(kv_grammar, line);
    *info = tree_to_dict(tree);
    cleri_parse_free(tree);

    char *props;
    for (DictEntry *entry = *info; entry; entry = entry->next) {
        if (! strcmp(entry->key, "Properties")) {
            props = entry->first_data->data.s;
            break;
        }
    }

    *arrays = (Arrays *) 0;
    char re[10240];
    re[0] = 0;

    Arrays *cur_array;

    char *pf = strtok(props, ":");
    while (pf) {
        if (! *arrays) {
            *arrays = (Arrays *) malloc(sizeof(Arrays));
            cur_array = *arrays;
        } else {
            Arrays *new_array = (Arrays *) malloc(sizeof(Arrays));
            cur_array->next = new_array;
            cur_array = cur_array->next;
        }

        cur_array->key = (char *) malloc((1+strlen(pf))*sizeof(char));
        strcpy(cur_array->key, pf);
        cur_array->next = 0;

        // advance to col type
        pf = strtok(NULL, ":");
        char col_type = pf[0];

        // advance to col num
        pf = strtok(NULL, ":");
        int col_num = atoi(pf);

        cur_array->nrows = nat;
        cur_array->ncols = col_num;

        char *this_re;
        char *this_fmt;
        switch (col_type) {
            case 'I':
                cur_array->data_t = data_i;
                cur_array->data.i = (int *) malloc((nat*col_num)*sizeof(int));
                this_re = "[+-]?[0-9]+";
                this_fmt = "%d";
                break;
            case 'R':
                cur_array->data_t = data_f;
                cur_array->data.f = (double *) malloc((nat*col_num)*sizeof(double));
                this_re = "[+-]?(?:[0-9]+[.]?[0-9]*|\\.[0-9]+)(?:[dDeE][+-]?[0-9]+)?";
                this_fmt = "%lf";
                break;
            case 'L':
                cur_array->data_t = data_b;
                cur_array->data.b = (int *) malloc((nat*col_num)*sizeof(int));
                this_re="[TF]";
                this_fmt = "%c";
                break;
            case 'S':
                cur_array->data_t = data_s;
                cur_array->data.s = (char **) malloc((nat*col_num)*sizeof(char *));
                this_re="\\S+";
                this_fmt="%s";
                break;
        }


        for (int ci=0; ci < col_num; ci++) {
            strcat(re, "(");
            strcat(re, this_re);
            strcat(re, ")");
            strcat(re,"\\s+");
        }

        // ready to next triplet
        pf = strtok(NULL, ":");
    }

    // for (
    for (int li=0; li < nat; li++) {
        fgets(line, 10239, fp);

        char *pf = strtok(line, " ");
        for (Arrays *cur_array = *arrays; cur_array; cur_array = cur_array->next) {
            int nc = cur_array->ncols;
            for (int col_i = 0; col_i < nc; col_i++) {
                if (cur_array->data_t == data_i) {
                    sscanf(pf, "%d", cur_array->data.i + li*nc + col_i);
                } else if (cur_array->data_t == data_f) {
                    sscanf(pf, "%lf", cur_array->data.f + li*nc + col_i);
                } else if (cur_array->data_t == data_b) {
                    char c;
                    sscanf(pf, "%c", &c);
                    cur_array->data.b[li*nc + col_i] = (c == 'T');
                } else if (cur_array->data_t == data_s) {
                    cur_array->data.s[li*nc + col_i] = (char *) malloc((strlen(pf)+1)*sizeof(char));
                    strcat(cur_array->data.s[li*nc+col_i], pf);
                }
                pf = strtok(NULL, " ");
            }
        }
    }

    return 1;
}

int main(int argc, char *argv[]) {
    FILE *fp;
    char line[10240];

    cleri_grammar_t * kv_grammar = compile_extxyz_kv_grammar();

    if (argc != 2) {
        fprintf(stderr, "Usage: %s in.xyz\n", argv[0]);
        exit(1);
    }

    int n_config = 0;

    DictEntry *info;
    Arrays *arrays;
    fp = fopen(argv[1], "r");
    while (extxyz_read(kv_grammar, fp, &info, &arrays)) {

        for (DictEntry *entry = info; entry; entry = entry->next) {
            printf("info '%s' type %d shape %d %d\n", entry->key, entry->data_t,
                   entry->nrows, entry->ncols);
        }
        for (Arrays *entry = arrays; entry; entry = entry->next) {
            printf("array '%s' type %d shape %d %d\n", entry->key, entry->data_t,
                   entry->nrows, entry->ncols);

        }

        printf("\n");

        n_config++;
        if (n_config % 1000 == 0) {
            fprintf(stderr, ".");
            fflush(stderr);
        }
    }
    fprintf(stderr, "\n");

    cleri_grammar_free(kv_grammar);

    return 0;
}
