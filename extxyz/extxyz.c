#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PCRE2_CODE_UNIT_WIDTH 8
#include <pcre2.h>
#include <cleri/cleri.h>

#include "extxyz_kv_grammar.h"
#include "extxyz.h"

#define MAX_RE_LEN 10240

void init_DictEntry(DictEntry *entry, const char *key, const int key_len) {
    if (key) {
        if (key_len <= 0) {
            fprintf(stderr, "INTERNAL ERROR: init_DictEntry with key '%s' and key_len %d <= 0\n", key, key_len);
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

double atof_eEdD(char *str) {
    for (int i=0; i < strlen(str); i++) {
        if (str[i] == 'd' || str[i] == 'D') {
            str[i] = 'e';
            break;
        }
    }
    return (atof(str));
}

void unquote(char *str) {
    // remove quotes and do backslash escapes
    int output_len = 0;
    for (char *si = str+1, *so = str; *(si+1) != 0; si++) {
        if (*si == '\\') {
            if (*(si+1) == 'n') {
                char *newline = "\n";
                for (char *c = newline; *c; c++) {
                    output_len++;
                    *so = *c;
                    so++;
                }
                si++;
            } if (*(si+1) == '\\') {
                *so = '\\';
                output_len++;
                si++;
                so++;
            }
            continue;
        }
        if (so != si) {
            *so = *si;
            output_len++;
        }
        so++;
    }
    str[output_len] = 0;
}

int parse_tree(cleri_node_t *node, DictEntry **cur_entry, int *in_seq, int *in_kv_pair, int *in_old_one_d) {
    //DEBUG printf("enter parse_tree in_kv_pair %d\n", *in_kv_pair); //DEBUG
    //DEBUG if (node->cl_obj) { //DEBUG
        //DEBUG printf("node type %d gid %d", node->cl_obj->tp, node->cl_obj->gid); //DEBUG
        //DEBUG if (1) { // node->cl_obj->tp == CLERI_TP_KEYWORD || node->cl_obj->tp == CLERI_TP_REGEX) { //DEBUG
            //DEBUG char *str = (char *) malloc((node->len+1) * sizeof(char)); //DEBUG
            //DEBUG strncpy(str, node->str, node->len); //DEBUG
            //DEBUG str[node->len] = 0; //DEBUG
//DEBUG  //DEBUG
            //DEBUG printf(" %s", str); //DEBUG
//DEBUG  //DEBUG
            //DEBUG free(str); //DEBUG
        //DEBUG } //DEBUG
        //DEBUG printf("\n"); //DEBUG
    //DEBUG } //DEBUG

    if (*in_kv_pair) {
        //DEBUG printf("in entry, looking for data\n"); //DEBUG
        // have key, looking for data

        if (node->cl_obj && (node->cl_obj->gid == CLERI_GID_OLD_ONE_D_ARRAY)) {
            // noting entry into old one-d array
            *in_old_one_d = 1;
        }
        if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_SEQUENCE)) {
            // entering sequence, increment depth counter
            (*in_seq)++;
            //DEBUG printf("sequence, new in_seq %d\n", *in_seq); //DEBUG
        } else if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_KEYWORD ||
                                    node->cl_obj->tp == CLERI_TP_REGEX)) {
            // something that contains actual data (keyword or regex)
            //DEBUG printf("FOUND keyword or regex\n"); //DEBUG
            DataLinkedList *new_data_ll = (DataLinkedList *) malloc(sizeof(DataLinkedList));
            if (! (*cur_entry)->first_data_ll) {
                // no data here yet
                (*cur_entry)->first_data_ll = new_data_ll;
            } else {
                // extend datalist
                (*cur_entry)->last_data_ll->next = new_data_ll;
            }
            (*cur_entry)->last_data_ll = new_data_ll;
            new_data_ll->data_t = data_none;
            new_data_ll->next = 0;
            (*cur_entry)->n_in_row++;

            if (node->cl_obj->tp == CLERI_TP_REGEX) {
                // parse things from regex: int, float, string
                // copy into null-terminated string, since cleri just
                // gives start pointer and length
                char * str = (char *) malloc((node->len+1)*sizeof(char));
                strncpy(str, node->str, node->len);
                str[node->len] = 0;

                if (node->cl_obj->gid == CLERI_GID_R_TRUE || node->cl_obj->gid == CLERI_GID_R_FALSE) {
                    //DEBUG printf("FOUND keyword bool\n"); //DEBUG
                    new_data_ll->data.b = (node->cl_obj->gid == CLERI_GID_R_TRUE);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    new_data_ll->data_t = data_b;
                    free(str);
                } else if (node->cl_obj->gid == CLERI_GID_R_INTEGER) {
                    //DEBUG printf("FOUND int\n"); //DEBUG
                    new_data_ll->data.i = atoi(str);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    new_data_ll->data_t = data_i;
                    free(str);
                } else if (node->cl_obj->gid == CLERI_GID_R_FLOAT) {
                    //DEBUG printf("FOUND float\n"); //DEBUG
                    new_data_ll->data.f = atof_eEdD(str);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    new_data_ll->data_t = data_f;
                    free(str);
                } else if (node->cl_obj->gid == CLERI_GID_R_STRING || 
                           node->cl_obj->gid == CLERI_GID_R_BARESTRING || 
                           node->cl_obj->gid == CLERI_GID_R_DQ_QUOTEDSTRING ||
                           node->cl_obj->gid == CLERI_GID_R_CB_QUOTEDSTRING ||
                           node->cl_obj->gid == CLERI_GID_R_SB_QUOTEDSTRING ||
                           node->cl_obj->gid == CLERI_GID_PROPERTIES_VAL_STR) {
                    // is it bad to just use CLERI_GID_PROPERTIES_VAL_STR as though it's a plain string?
                    //DEBUG printf("FOUND string\n"); //DEBUG
                    // store pointer, do not copy, but data was still allocated
                    // in this routine, not in cleri parsing.
                    if (node->cl_obj->gid == CLERI_GID_R_DQ_QUOTEDSTRING ||
                        node->cl_obj->gid == CLERI_GID_R_CB_QUOTEDSTRING ||
                        node->cl_obj->gid == CLERI_GID_R_SB_QUOTEDSTRING) {
                        unquote(str);
                    }
                    new_data_ll->data.s = str;
                    new_data_ll->data_t = data_s;
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
                /*
                if (node->cl_obj->gid == CLERI_GID_K_TRUE || node->cl_obj->gid == CLERI_GID_K_FALSE) {
                    //DEBUG printf("FOUND keyword bool\n"); //DEBUG
                    new_data_ll->data.b = (node->cl_obj->gid == CLERI_GID_K_TRUE);
                    // not checking for mismatch, parsing should make sure data type is consistent
                    new_data_ll->data_t = data_b;
                } else {
                */
                    // allocate string for printing
                    char * str = (char *) malloc((node->len+1)*sizeof(char));
                    strncpy(str, node->str, node->len);
                    fprintf(stderr, "Failed to parse some keyword as data, key '%s' str '%s'\n", (*cur_entry)->key, str);
                    free(str);
                    return 1;
                /*
                }
                */
            }

            if (*in_seq == 0) {
                // end of a scalar, not longer in a k-v pair
                //DEBUG printf("got scalar, setting in_kv_pair=0\n"); //DEBUG
                *in_kv_pair = 0;
            }
        }
    } else {
        //DEBUG printf("looking for key\n"); //DEBUG
        // looking for key
        if (node->cl_obj && (node->cl_obj->tp == CLERI_TP_KEYWORD ||
                             node->cl_obj->tp == CLERI_TP_REGEX)) {
            // only keywords and regex can be keys
            if (node->len == 0) {
                // empty regex, skip
                return 0;
            }
            //DEBUG printf("got key, setting in_kv_pair=1\n"); //DEBUG
            *in_kv_pair = 1;
            // found something that can contain key
            if ((*cur_entry)->key) {
                // non-zero key indicates a real dict entry, extend linked list
                DictEntry *new_entry = (DictEntry *) malloc(sizeof(DictEntry));
                (*cur_entry)->next = new_entry;
                (*cur_entry) = new_entry;
            }
            if (node->cl_obj->gid == CLERI_GID_R_DQ_QUOTEDSTRING ||
                node->cl_obj->gid == CLERI_GID_R_CB_QUOTEDSTRING ||
                node->cl_obj->gid == CLERI_GID_R_SB_QUOTEDSTRING) {
                char *str = (char *) malloc((node->len+1) * sizeof(char));
                strncpy(str, node->str, node->len);
                str[node->len] = 0;
                //DEBUG printf("got quoted str '%s'\n", str); //DEBUG
                unquote(str);
                //DEBUG printf("got unquoted str '%s'\n", str); //DEBUG
                init_DictEntry(*cur_entry, str, node->len);
                free(str);
            } else {
                init_DictEntry(*cur_entry, node->str, node->len);
            }
            //DEBUG printf("got key '%s'\n", (*cur_entry)->key); //DEBUG
            // key containing nodes never have children, so return now
            return 0;
        }
    }

    //DEBUG printf("looping over children\n"); //DEBUG
    for (cleri_children_t *child = node->children; child; child = child->next) {
        //DEBUG printf("child\n"); //DEBUG
        int err = parse_tree(child->node, cur_entry, in_seq, in_kv_pair, in_old_one_d);
        if (err) {
            return err;
        }
    }

    if (node->cl_obj && (node->cl_obj->gid == CLERI_GID_OLD_ONE_D_ARRAY)) {
        // noting exit from into old one-d array
        *in_old_one_d = 0;
    }
    if (node->cl_obj && node->cl_obj->tp == CLERI_TP_SEQUENCE) {
        //DEBUG printf("leaving sequence\n"); //DEBUG
        if (*in_seq == 2) {
            //DEBUG printf("leaving inner row\n"); //DEBUG
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
            //DEBUG printf("leaving outer row\n"); //DEBUG
            if ((*cur_entry)->ncols == 0) {
                // Exiting sequence and ncols is still 0, so list was not nested.
                // Need to store ncols here.
                if (*in_old_one_d && (*cur_entry)->n_in_row == 1) {
                    // special case old 1-d arrays with one entry as scalar
                    (*cur_entry)->ncols = 0;
                } else if (*in_old_one_d && (*cur_entry)->n_in_row == 9) {
                    // special case old 1-d arrays with 9 entries as 3x3
                    // negative value is ugly hack to indicate that data should be transposed
                    (*cur_entry)->ncols = -3;
                    (*cur_entry)->nrows = -3;
                } else {
                    // 1-d array
                    (*cur_entry)->ncols = (*cur_entry)->n_in_row;
                }
                (*cur_entry)->n_in_row = 0;
            }
            // exiting sequence
            (*in_seq)--;
            //DEBUG printf("exiting top level sequence, setting in_kv_pair=0\n"); //DEBUG
            // this is maybe not the best way of figuring out if you're leaving a 
            // key-value pair, but since everything is either a scalar or sequence
            // it's OK for now
            *in_kv_pair = 0;
        }
    }

    //DEBUG printf("leaving parse\n"); //DEBUG
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
        printf("%snode NULL\n", prefix);
    }

    for (cleri_children_t *child = node->children; child; child = child->next) {
        dump_tree(child->node, new_prefix);
    }

    free(new_prefix);
}


int opt_transpose(int i, int nrows, int ncols) {
    if (nrows < 0 || ncols < 0) {
        // < 0 indicates a transpose (e.g. old-style 9-elem vector -> 3x3)
        int icol = i / abs(ncols);
        int irow = i % abs(ncols);
        return irow*abs(nrows) + icol;
    } else{
        return i;
    }
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


int DataLinkedList_to_data(DictEntry *dict) {
    int stat=0;

    for (DictEntry *entry = dict; entry; entry = entry->next) {
        if (! entry->first_data_ll) {
            // no linked list, nothing to copy
            continue;
        }

        DataLinkedList *data_item = entry->first_data_ll;
        int n_items;
        enum data_type data_t = data_none;
        // count items and check for data type consistency
        for (n_items=0; data_item; n_items++, data_item = data_item->next) {
            if (data_t == data_none) {
                // no prev data type set yet, set it now
                data_t = data_item->data_t;
            } else if (data_item->data_t == data_i || data_item->data_t == data_f) {
                // this item is a number
                if (data_t != data_i && data_t != data_f) {
                    // prev data is not a number, fail
                    if (!stat) {
                        fprintf(stderr, "ERROR: in an array got a number type %d after a non-number %d\n",
                            data_item->data_t, data_t);
                    }
                    stat=1;
                }
                if (data_item->data_t == data_f || data_t == data_f) {
                    // if any float appears, overall is a float
                    data_t = data_f;
                }
            } else if (data_item->data_t != data_t) {
                if (!stat) {
                    fprintf(stderr, "ERROR: in an array got a change in type from %d to %dthat cannot be promoted\n",
                        data_t, data_item->data_t);
                }
                stat=1;
            }
        }

        if (stat == 0) {
            entry->data_t = data_t;
            data_item = entry->first_data_ll;
            // no checking for valid data_item in loops below because loop
            // iters were checked using empty data_item loop above
            if (entry->data_t == data_i) {
                entry->data = (int *) malloc(n_items*sizeof(int));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    ((int *)(entry->data))[opt_transpose(i, entry->nrows, entry->ncols)] = data_item->data.i;
                }
            } else if (entry->data_t == data_f) {
                entry->data = (double *) malloc(n_items*sizeof(double));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    if (data_item->data_t == data_f) {
                        ((double *)(entry->data))[opt_transpose(i, entry->nrows, entry->ncols)] = data_item->data.f;
                    } else {
                        ((double *)(entry->data))[opt_transpose(i, entry->nrows, entry->ncols)] = data_item->data.i;
                    }
                }
            } else if (entry->data_t == data_b) {
                entry->data = (int *) malloc(n_items*sizeof(int));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    ((int *)(entry->data))[opt_transpose(i, entry->nrows, entry->ncols)] = data_item->data.b;
                }
            } else if (entry->data_t == data_s) {
                // allocate array of char pointers, but actual string content
                // will be just copied pointers
                entry->data = (char **) malloc(n_items*sizeof(char *));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    ((char **)(entry->data))[opt_transpose(i, entry->nrows, entry->ncols)] = data_item->data.s;
                }
            }
            if (entry->nrows < 0 || entry->ncols < 0) {
                // < 0 indicates a transpose is needed
                int t = abs(entry->nrows);
                entry->nrows = abs(entry->ncols);
                entry->ncols = t;
            }
        }

        // free data linked list, but keep strings allocated, since their
        // pointers were copied to data
        free_DataLinkedList(entry->first_data_ll, entry->data_t, 0);
        entry->first_data_ll = 0;
        entry->last_data_ll = 0;
    }

    return stat;
}


void *tree_to_dict(cleri_parse_t *tree) {
    //DEBUG dump_tree(tree->tree, ""); //DEBUG
    // printf("END DUMP\n");

    DictEntry *dict = (DictEntry *) malloc(sizeof(DictEntry));
    // initialize empty dict entry with no key
    init_DictEntry(dict, 0, -1);

    DictEntry *cur_entry = dict;

    int in_seq = 0, in_kv_pair = 0, in_old_one_d = 0;
    int err;
    err = parse_tree(tree->tree, &cur_entry, &in_seq, &in_kv_pair, &in_old_one_d);
    if (err) {
        fprintf(stderr, "error parsing tree\n");
        return 0;
    }

    err = DataLinkedList_to_data(dict);
    if (err) {
        fprintf(stderr, "ERROR converting data linked list to data arrays, probably inconsistent data types\n");
        return 0;
    }

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
void strcat_realloc(char **str, int *len, char *add_str) {
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
            fprintf(stderr, "ERROR: failed to realloc in read_line\n");
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
        fprintf(stderr, "Failed to parse string at pos %zd\n", tree->pos);
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
    if ((*info)->key) {
        // only try if first entry has key, otherwise must have parsed nothing
        for (DictEntry *entry = *info; entry; entry = entry->next) {
            if (! strcmp(entry->key, "Properties")) {
                // copy into props, so strtok doesn't modify copy in info dict
                char *p = ((char **)(entry->data))[0];
                props = (char *) malloc((strlen(p)+1)*sizeof(char));
                strcpy(props, p);
                break;
            }
        }
    } else {
        // nothing parsable, just store line in "comment" dict entry
        init_DictEntry(*info, "comment", strlen("comment"));
        (*info)->data = (char **) malloc(sizeof(char *));
        ((char **)(*info)->data)[0] = (char *) malloc((strlen(line)+1) * sizeof(char));
        // remove eol
        if (strlen(line) >= strlen("\n")) {
            char *eol = "\n";
            int match=1;
            for (int i=0; i < strlen(eol); i++) {
                if (line[strlen(line)-i] != eol[strlen(eol)-i]) {
                    match=0;
                    break;
                }
            }
            if (match) {
                line[strlen(line)-strlen(eol)] = 0;
            }
        }
        strcpy(((char **)(*info)->data)[0], line);
        (*info)->data_t = data_s;
    }
    if (! props) {
        // either nothing parsed, or something parsed but no Properties
        // should we assume default xyz instead, and if so species or Z, or just species?
        char *p = "species:S:1:pos:R:3";
        props = (char *) malloc((strlen(p)+1)*sizeof(char));
        strcpy(props, p);
        // fprintf(stderr, "ERROR: failed to find Properties keyword");
        // free(line);
        // return 0;
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
            free(props);
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
            free(props);
            free(line); free(re_str);
            return 0;
        }

        // make an nat x ncol matrix
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
                free(props);
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

    free(props);

    // trim off last \s+
    re_str[strlen(re_str)-3] = 0;
    // tack on to EOL
    strcat_realloc(&re_str, &re_str_len, re_at_eol);

    // should consider doing string types more carefully, e.g. as shown in
    // https://www.pcre.org/current/doc/html/pcre2demo.html 
    // with PCRE2_SPTR
    int pcre2_error;
    PCRE2_SIZE erroffset;
    pcre2_code *re = pcre2_compile(re_str, PCRE2_ZERO_TERMINATED, 0, &pcre2_error, &erroffset, NULL);
    if (pcre2_error != 0) {
        fprintf(stderr, "ERROR compiling pcre pattern for atoms lines offset %d re '%s'\n", erroffset, re_str);
    }
    pcre2_match_data *match_data;
    match_data = pcre2_match_data_create_from_pattern(re, NULL);

    // read per-atom data
    for (int li=0; li < (*nat); li++) {
        stat = read_line(&line, &line_len, fp);
        if (! stat) {
            pcre2_match_data_free(match_data); pcre2_code_free(re);
            free(line); free(re_str);
            return 0;
        }

        // read data with PCRE + atoi/f
        // apply PCRE
        int rc = pcre2_match(re, line, PCRE2_ZERO_TERMINATED, 0, 0, match_data, NULL);
        if (rc != tot_col_num+1) {
            if (rc < 0) {
                if (rc == PCRE2_ERROR_NOMATCH) {
                    fprintf(stderr, "ERROR: pcre2 regexp got NOMATCH on atom line %d\n", li);
                } else {
                    fprintf(stderr, "ERROR: pcre2 regexp got error %d on atom line %d %d\n", rc, li);
                }
            } else if (rc == 0) {
                fprintf(stderr, "ERROR: pcre2 regexp got match_data not big enough (should never happen) on atom line %d %d\n", li);
            } else {
                fprintf(stderr, "ERROR: pcre2 regexp failed on atom line %d at group %d\n", li, rc-1);
            }
            pcre2_match_data_free(match_data); pcre2_code_free(re);
            free(line); free(re_str);
            return 0;
        }
        // loop through parsed strings and fill in allocated data structures
        PCRE2_SIZE *ovector = pcre2_get_ovector_pointer(match_data);
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
                    ((double *)(cur_array->data))[li*nc + col_i] = atof_eEdD(pf);
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

    // convert per-atom nat x 1 array to nat-long vector
    for (DictEntry *cur_array = *arrays; cur_array; cur_array = cur_array->next) {
        if (cur_array->ncols == 1) {
            cur_array->ncols = cur_array->nrows;
            cur_array->nrows = 0;
        }
    }

    // return true
    pcre2_match_data_free(match_data); pcre2_code_free(re);
    free(line); free(re_str);
    return 1;
}
