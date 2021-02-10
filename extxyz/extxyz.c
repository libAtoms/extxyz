#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <pcre.h>
#include <cleri/cleri.h>

#include "extxyz_kv_grammar.h"
#include "extxyz.h"

#define MAX_RE_LEN 10240

void init_DictEntry(DictEntry *entry, const char *key, const int key_len) {
    if (key) {
        if (key_len <= 0) {
            fprintf(stderr, "INTERNAL ERROR: init_DictEntry with key %d and key_len %d <= 0\n", key, key_len);
            exit(1);
        }
        // copy into entry
        char *str = (char *) malloc((key_len+1)*sizeof(char));
        strncpy(str, key, key_len);
        str[key_len] = 0;
        entry->key = str;
    } else {
        entry->key = 0;
    }
    entry->nrows = entry->ncols = entry->n_in_row = 0;
    entry->first_data_ll = entry->last_data_ll = 0;
    entry->data = 0;
    entry->data_t = data_none;
    entry->next = 0;
}

int parse_tree(cleri_node_t *node, DictEntry **cur_entry, int *in_seq, int *in_kv_pair) {
    //DEBUG printf("enter parse_tree in_kv_pair %d\n", *in_kv_pair);
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

    if (*in_kv_pair) {
        //DEBUG printf("in entry, looking for data\n");
        // have key, looking for data
        if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_SEQUENCE)) {
            // entering sequence, increment depth counter
            (*in_seq)++;
            //DEBUG printf("sequence, new in_seq %d\n", *in_seq);
        } else if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_KEYWORD ||
                                    node->cl_obj->tp == CLERI_TP_REGEX)) {
            // something that contains actual data (keyword or regex)
            //DEBUG printf("FOUND keyword or regex\n");
            DataLinkedList *new_data_ll = (DataLinkedList *) malloc(sizeof(DataLinkedList));
            if (! (*cur_entry)->first_data_ll) {
                // no data here yet
                (*cur_entry)->first_data_ll = new_data_ll;
            } else {
                // extend datalist
                (*cur_entry)->last_data_ll->next = new_data_ll;
            }
            (*cur_entry)->last_data_ll = new_data_ll;
            new_data_ll->next = 0;
            (*cur_entry)->n_in_row++;

            if (node->cl_obj->tp == CLERI_TP_REGEX) {
                // parse things from regex: int, float, string
                // copy into null-terminated string, since cleri just
                // gives start pointer and length
                char * str = (char *) malloc((node->len+1)*sizeof(char));
                strncpy(str, node->str, node->len);
                str[node->len] = 0;

                if (node->cl_obj->gid == CLERI_GID_R_INTEGER) {
                    //DEBUG printf("FOUND int\n");
                    new_data_ll->data.i = atoi(str);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    (*cur_entry)->data_t = data_i;
                    free(str);
                } else if (node->cl_obj->gid == CLERI_GID_R_FLOAT) {
                    //DEBUG printf("FOUND float\n");
                    new_data_ll->data.f = atof(str);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    (*cur_entry)->data_t = data_f;
                    free(str);
                } else if (node->cl_obj->gid == CLERI_GID_R_STRING || 
                           node->cl_obj->gid == CLERI_GID_R_BARESTRING || 
                           node->cl_obj->gid == CLERI_GID_R_QUOTEDSTRING ||
                           node->cl_obj->gid == CLERI_GID_PROPERTIES_VAL_STR) {
                    // is it bad to just use CLERI_GID_PROPERTIES_VAL_STR as though it's a plain string?
                    //DEBUG printf("FOUND string\n");
                    // store pointer, do not copy, but data was still allocated
                    // in this routine, not in cleri parsing.
                    new_data_ll->data.s = str;
                    (*cur_entry)->data_t = data_s;
                } else {
                    // ignore blank regex, they show up sometimes e.g. after end of sequence
                    if (strlen(str) > 0) {
                        fprintf(stderr, "Failed to parse some regex as data key '%s' str '%s'\n", 
                                (*cur_entry)->key, str);
                        // free before incomplete return
                        free(str);
                        return 1;
                    }
                }
            } else {
                // keyword
                if (node->cl_obj->gid == CLERI_GID_K_TRUE || node->cl_obj->gid == CLERI_GID_K_FALSE) {
                    //DEBUG printf("FOUND keyword bool\n");
                    new_data_ll->data.b = (node->cl_obj->gid == CLERI_GID_K_TRUE);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    (*cur_entry)->data_t = data_b;
                } else {
                    // allocate string for printing
                    char * str = (char *) malloc((node->len+1)*sizeof(char));
                    strncpy(str, node->str, node->len);
                    fprintf(stderr, "Failed to parse some keyword as data, key '%s' str '%s'\n", (*cur_entry)->key, str);
                    free(str);
                    return 1;
                }
            }

            if (*in_seq == 0) {
                // end of a scalar, not longer in a k-v pair
                //DEBUG printf("got scalar, setting in_kv_pair=0\n");
                *in_kv_pair = 0;
            }
        }
    } else {
        //DEBUG printf("looking for key\n");
        // looking for key
        if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_KEYWORD ||
                             node->cl_obj->tp == CLERI_TP_REGEX)) {
            // only keywords and regex can be keys
            if (node->len == 0) {
                // empty regex, skip
                return 0;
            }
            //DEBUG printf("got key, setting in_kv_pair=1\n");
            *in_kv_pair = 1;
            //DEBUG printf("FOUND keyword or regex\n");
            // found something that can contain key
            if ((*cur_entry)->key) {
                // non-zero key indicates a real dict entry, extend linked list
                DictEntry *new_entry = (DictEntry *) malloc(sizeof(DictEntry));
                (*cur_entry)->next = new_entry;
                (*cur_entry) = new_entry;
            }
            init_DictEntry(*cur_entry, node->str, node->len);
            //DEBUG printf("got key '%s'\n", (*cur_entry)->key);
            // key containing nodes never have children, so return now
            return 0;
        }
    }

    //DEBUG printf("looping over children\n");
    for (cleri_children_t *child = node->children; child; child = child->next) {
        //DEBUG printf("child\n");
        int err = parse_tree(child->node, cur_entry, in_seq, in_kv_pair);
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
                // not first row, check for consistency
                fprintf(stderr, "key %s nested list row %d number of entries in row %d inconsistent with prev %d\n", 
                        (*cur_entry)->key, (*cur_entry)->nrows+1, (*cur_entry)->n_in_row, (*cur_entry)->ncols);
                return 1;
            }
            (*cur_entry)->nrows++;
            (*cur_entry)->ncols = (*cur_entry)->n_in_row;
            (*cur_entry)->n_in_row = 0;
            // decrease nested sequence depth
            (*in_seq)--;
        } else if (*in_seq == 1) {
            //DEBUG printf("leaving outer row\n");
            if ((*cur_entry)->ncols == 0) {
                // Exiting sequence and ncols is still 0, so list was not nested.
                // Need to store ncols here.
                (*cur_entry)->ncols = (*cur_entry)->n_in_row;
                (*cur_entry)->n_in_row = 0;
            }
            // exiting sequence
            (*in_seq)--;
            //DEBUG printf("exiting top level sequence, setting in_kv_pair=0\n");
            // this is maybe not the best way of figuring out if you're leaving a 
            // key-value pair, but since everything is either a scalar or sequence
            // it's OK for now
            *in_kv_pair = 0;
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


void free_DataLinkedList(DataLinkedList *list, enum data_type data_t, int free_string_content) {
    if (!list) {
        return;
    }

    DataLinkedList *next_data;
    for (DataLinkedList *data = list; data; data = next_data) {
        if (data_t == data_s && free_string_content) {
            free(data->data.s);
        }
        next_data = data->next;
        free(data);
    }
}


void DataLinkedList_to_data(DictEntry *dict) {
    for (DictEntry *entry = dict; entry; entry = entry->next) {
        if (entry->first_data_ll) {
            // has linked list contents
            DataLinkedList *data_item = entry->first_data_ll;
            int n_items;
            for (n_items=0; data_item; n_items++, data_item = data_item->next) {
            }
            data_item = entry->first_data_ll;
            // no checking for valid data_item in loops below because loop
            // iters were checked using empty data_item loop above
            if (entry->data_t == data_i) {
                entry->data = (int *) malloc(n_items*sizeof(int));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    ((int *)(entry->data))[i] = data_item->data.i;
                }
            } else if (entry->data_t == data_f) {
                entry->data = (double *) malloc(n_items*sizeof(double));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    ((double *)(entry->data))[i] = data_item->data.f;
                }
            } else if (entry->data_t == data_b) {
                entry->data = (int *) malloc(n_items*sizeof(int));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    ((int *)(entry->data))[i] = data_item->data.b;
                }
            } else if (entry->data_t == data_s) {
                // allocate array of char pointers, but actual string content
                // will be just copied pointers
                entry->data = (char **) malloc(n_items*sizeof(char *));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    ((char **)(entry->data))[i] = data_item->data.s;
                }
            }

            // free data linked list, but keep strings allocated, since their
            // pointers were copied to data
            free_DataLinkedList(entry->first_data_ll, entry->data_t, 0);
            entry->first_data_ll = 0;
            entry->last_data_ll = 0;
        }
    }
}


void *tree_to_dict(cleri_parse_t *tree) {
    // dump_tree(tree->tree, "");
    // printf("END DUMP\n");

    DictEntry *dict = (DictEntry *) malloc(sizeof(DictEntry));
    // initialize empty dict entry with no key
    init_DictEntry(dict, 0, -1);

    DictEntry *cur_entry = dict;

    int in_seq = 0, in_kv_pair = 0;
    int err = parse_tree(tree->tree, &cur_entry, &in_seq, &in_kv_pair);
    if (err) {
        fprintf(stderr, "error parsing tree\n");
        return 0;
    }

    DataLinkedList_to_data(dict);

    return dict;
}


void free_data(void *data, enum data_type data_t, int nrows, int ncols) {
    if (!data) {
        return;
    }
    if (data_t == data_s) {
        // free allocated strings inside array
        nrows = nrows == 0 ? 1 : nrows;
        ncols = ncols == 0 ? 1 : ncols;
        for (int ri=0; ri < nrows; ri++) {
        for (int ci=0; ci < ncols; ci++) {
            free(((char **)data)[ri*ncols + ci]);
        }
        }
    }
    free(data);
}


void free_dict(DictEntry *dict) {
    DictEntry *next_entry = dict->next;
    for (DictEntry *entry = dict; entry; entry = next_entry) {
        if (entry->key) {
            free(entry->key);
        }
        free_DataLinkedList(entry->first_data_ll, entry->data_t, 1);
        free_data(entry->data, entry->data_t, entry->nrows, entry->ncols); 

        next_entry = entry->next;
        free(entry);
    }
}

void print_dict(DictEntry *dict) {
    for (DictEntry *entry = dict; entry; entry = entry->next) {
        printf("key '%s' type %d shape %d %d\n", entry->key, entry->data_t,
               entry->nrows, entry->ncols);
    }
}


#define STR_INCR 1024
char *strcat_realloc(char **str, int *len, char *add_str) {
    if (strlen(*str) + strlen(add_str) + 1 > *len) {
        *len += STR_INCR;
        *str = (char *) realloc(*str, *len);
        if (!*str) {
            fprintf(stderr, "ERROR: failed to realloc in strcat_realloc\n");
            exit(1);
        }
    }
    strcat(*str, add_str);
}

char *read_line(char **line, int *line_len, FILE *fp) {
    char *stat = fgets(*line, *line_len, fp);
    if (!stat) {
        return 0;
    }
    while (strlen(*line) == *line_len-1) {
        *line_len += STR_INCR;
        *line = (char *) realloc(*line, *line_len * sizeof(char));
        if (!*line) {
            fprintf(stderr, "ERROR: failed to realloc in strcat_realloc\n");
            exit(1);
        }

        stat = fgets(*line + *line_len - STR_INCR - 1, STR_INCR, fp);
        if (!stat) {
            return 0;
        }
    }
    return *line;
}

int extxyz_read_ll(cleri_grammar_t *kv_grammar, FILE *fp, int *nat, DictEntry **info, DictEntry **arrays) {
    char *line;
    int line_len;
    int line_len_init = 1024;

    // from here on every return should free line first;
    line_len  = line_len_init;
    line = (char *) malloc(line_len * sizeof(char));

    // we could set this based on whether we want to default to 
    // traditional xyz, and so ignore extra columns, when Properties is 
    // missing
    char *re_at_eol = "\\s*$";
    // less restrictive alternative, allows for ignored extra columns
    // char *re_at_eol = "(?:\\s+|\\s*$)");

    // nat
    char *stat = read_line(&line, &line_len, fp);
    if (! stat) {
        free(line);
        return 0;
    }
    int nat_stat = sscanf(line, "%d", nat);
    if (nat_stat != 1) {
        fprintf(stderr, "Failed to parse int natoms from '%s'\n", line);
        free(line);
        return 0;
    }

    // info
    stat = read_line(&line, &line_len, fp);
    if (! stat) {
        free(line);
        return 0;
    }
    // actually parse
    cleri_parse_t * tree = cleri_parse(kv_grammar, line);
    if (! tree->is_valid) {
        fprintf(stderr, "Failed to parse string at pos %d\n", tree->pos);
        cleri_parse_free(tree);
        free(line);
        return 0;
    }
    *info = tree_to_dict(tree);
    cleri_parse_free(tree);
    if (! info) {
        fprintf(stderr, "Failed to convert tree to dict\n");
        free(line);
        return 0;
    }

    // grab and parse Properties string
    char *props = 0;
    for (DictEntry *entry = *info; entry; entry = entry->next) {
        if (! strcmp(entry->key, "Properties")) {
            props = ((char **)(entry->data))[0];
            break;
        }
    }
    if (! props) {
        // should we assume default xyz instead, and if so species or Z, or just species?
        fprintf(stderr, "ERROR: failed to find Properties keyword");
        free(line);
        return 0;
    }

    // from here on every return should also free re_str first;
    int re_str_len = 20;
    char *re_str = (char *) malloc (re_str_len * sizeof(char));
    re_str[0] = 0;
    strcat_realloc(&re_str, &re_str_len, "^\\s*");

    *arrays = (DictEntry *) 0;
    DictEntry *cur_array;

    char *pf = strtok(props, ":");
    int prop_i = 0, tot_col_num = 0;
    while (pf) {
        if (! *arrays) {
            *arrays = (DictEntry *) malloc(sizeof(DictEntry));
            cur_array = *arrays;
        } else {
            DictEntry *new_array = (DictEntry *) malloc(sizeof(DictEntry));
            cur_array->next = new_array;
            cur_array = cur_array->next;
        }

        init_DictEntry(cur_array, pf, strlen(pf));

        // advance to col type
        pf = strtok(NULL, ":");
        if (strlen(pf) != 1) {
            fprintf(stderr, "Failed to parse property type '%s' for property '%s' (# %d)\n", pf, cur_array->key, prop_i);
            free(line); free(re_str);
            return 0;
        }
        char col_type = pf[0];

        // advance to col num
        pf = strtok(NULL, ":");
        int col_num;
        int col_num_stat = sscanf(pf, "%d", &col_num);
        if (col_num_stat != 1) {
            fprintf(stderr, "Failed to parse int property ncolumns from '%s' for property '%s' (# %d)\n", pf, cur_array->key, prop_i);
            free(line); free(re_str);
            return 0;
        }

        cur_array->nrows = *nat;
        cur_array->ncols = col_num;

        char *this_re;
        switch (col_type) {
            case 'I':
                cur_array->data_t = data_i;
                cur_array->data = malloc(((*nat)*col_num)*sizeof(int));
                this_re = "[+-]?[0-9]+";
                break;
            case 'R':
                cur_array->data_t = data_f;
                cur_array->data = malloc(((*nat)*col_num)*sizeof(double));
                this_re = "[+-]?(?:[0-9]+[.]?[0-9]*|\\.[0-9]+)(?:[dDeE][+-]?[0-9]+)?";
                break;
            case 'L':
                cur_array->data_t = data_b;
                cur_array->data = malloc(((*nat)*col_num)*sizeof(int));
                this_re="(?:[TF]|[tT]rue|[fF]alse|TRUE|FALSE)";
                break;
            case 'S':
                cur_array->data_t = data_s;
                cur_array->data = malloc(((*nat)*col_num)*sizeof(char *));
                this_re="\\S+";
                break;
            default:
                fprintf(stderr, "Unknown property type '%c' for property key '%s' (# %d)\n", col_type, cur_array->key, prop_i);
                // free incomplete data before returning
                free(cur_array->data);
                cur_array->data = 0;
                free(line); free(re_str);
                return 0;
        }

        for (int ci=0; ci < col_num; ci++) {
            strcat_realloc(&re_str, &re_str_len, "(");
            strcat_realloc(&re_str, &re_str_len, this_re);
            strcat_realloc(&re_str, &re_str_len, ")");
            strcat_realloc(&re_str, &re_str_len, "\\s+");
        }

        // ready to next triplet
        pf = strtok(NULL, ":");
        prop_i++;
        tot_col_num += col_num;
    }

    // trim off last \s+
    re_str[strlen(re_str)-3] = 0;
    // tack on to EOL
    strcat_realloc(&re_str, &re_str_len, re_at_eol);

    const char *pcre_error;
    int erroffset;
    pcre *re = pcre_compile(re_str, 0, &pcre_error, &erroffset, NULL);
    if (pcre_error != 0) {
        fprintf(stderr, "ERROR compiling pcre pattern for atoms lines offset %d re '%s'\n", erroffset, re_str);
    }
    // this will not work with exactly 3*tot_col_num, for reasons that are
    // apparetntly explained in the PCRE docs 
    // ("There  are  some  cases where zero is returned"...)
    int ovector_len = 3*tot_col_num+3;
    int *ovector = (int *) malloc(ovector_len * sizeof(int));
    // pcre_study?

    // read per-atom data
    for (int li=0; li < (*nat); li++) {
        stat = read_line(&line, &line_len, fp);
        if (! stat) {
            free(line); free(re_str);
            return 0;
        }

        // use PCRE + atoi/f
        // printf("applying pcre to '%s'\n", line);
        int rc = pcre_exec(re, NULL, line, strlen(line), 0, 0, ovector, ovector_len);
        if (rc != tot_col_num+1) {
            if (rc > 0) {
                fprintf(stderr, "ERROR: failed to apply pcre regexp to atom line %d at subgroup %d\n", li, rc-1);
            } else {
                fprintf(stderr, "ERROR: failed to apply pcre regexp to atom line %d error %d\n", li, rc);
            }
            free(line); free(re_str);
            return 0;
        }
        int field_i = 1;
        for (DictEntry *cur_array = *arrays; cur_array; cur_array = cur_array->next) {
            int nc = cur_array->ncols;
            for (int col_i = 0; col_i < nc; col_i++) {
                pf = line + ovector[2*field_i];
                // overwrite end of field, must be at least one space so won't damage anything
                line[ovector[2*field_i+1]] = 0;
                if (cur_array->data_t == data_i) { 
                    ((int *)(cur_array->data))[li*nc + col_i] = atoi(pf);
                } else if (cur_array->data_t == data_f) {
                    ((double *)(cur_array->data))[li*nc + col_i] = atof(pf);
                } else if (cur_array->data_t == data_b) {
                    ((int *)(cur_array->data))[li*nc + col_i] = (pf[0] == 'T');
                } else if (cur_array->data_t == data_s) {
                    ((char **)(cur_array->data))[li*nc + col_i] = (char *) malloc((strlen(pf)+1)*sizeof(char));
                    strcpy(((char **)(cur_array->data))[li*nc+col_i], pf);
                }
                field_i++;
            }
        }
        /* {
            // use strtok + sscanf
            char *pf = strtok(line, " ");
            for (DictEntry *cur_array = *arrays; cur_array; cur_array = cur_array->next) {
                int nc = cur_array->ncols;
                for (int col_i = 0; col_i < nc; col_i++) {
                    if (cur_array->data_t == data_i) {
                        sscanf(pf, "%d", ((int *)(cur_array->data)) + li*nc + col_i);
                    } else if (cur_array->data_t == data_f) {
                        sscanf(pf, "%lf", ((double *)(cur_array->data)) + li*nc + col_i);
                    } else if (cur_array->data_t == data_b) {
                        char c;
                        sscanf(pf, "%c", &c);
                        ((int *)(cur_array->data))[li*nc + col_i] = (c == 'T');
                    } else if (cur_array->data_t == data_s) {
                        ((char **)(cur_array->data))[li*nc + col_i] = (char *) malloc((strlen(pf)+1)*sizeof(char));
                        strcpy(((char **)(cur_array->data))[li*nc+col_i], pf);
                    }
                    pf = strtok(NULL, " ");
                }
            }
        } */
    }

    // return true
    free(line); free(re_str);
    return 1;
}
