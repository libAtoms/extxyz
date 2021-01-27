#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cleri/cleri.h>

#include "extxyz_kv_grammar.h"
#include "extxyz.h"

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
            DataLinkedList *new_data = (DataLinkedList *) malloc(sizeof(DataLinkedList));
            if (! (*cur_entry)->first_data_ll) {
                // no data here yet
                (*cur_entry)->first_data_ll = new_data;
            } else {
                // extend datalist
                (*cur_entry)->last_data_ll->next = new_data;
            }
            (*cur_entry)->last_data_ll = new_data;
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
            (*cur_entry)->first_data_ll = (*cur_entry)->last_data_ll = 0;
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

void free_DataLinkedList(enum data_type data_t, DataLinkedList *list, int free_string_content) {
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


void DataLinkedList_to_DataPtr(DictEntry *dict) {
    for (DictEntry *entry = dict; entry; entry = entry->next) {
        if (entry->first_data_ll) {
            DataLinkedList *data_item = entry->first_data_ll;
            int n_items;
            for (n_items=0; data_item; n_items++, data_item = data_item->next) {
            }
            data_item = entry->first_data_ll;
            if (entry->data_t == data_i) {
                entry->data.i = (int *) malloc(n_items*sizeof(int));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    entry->data.i[i] = data_item->data.i;
                }
            } else if (entry->data_t == data_f) {
                entry->data.f = (double *) malloc(n_items*sizeof(double));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    entry->data.f[i] = data_item->data.f;
                }
            } else if (entry->data_t == data_b) {
                entry->data.b = (int *) malloc(n_items*sizeof(int));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    entry->data.b[i] = data_item->data.b;
                }
            } else if (entry->data_t == data_s) {
                entry->data.s = (char **) malloc(n_items*sizeof(char *));
                for (int i=0; i < n_items; i++, data_item = data_item->next) {
                    entry->data.s[i] = data_item->data.s;
                }
            }

            // free data linked list, but keep strings allocated, since they were 
            // copied to data
            free_DataLinkedList(entry->data_t, entry->first_data_ll, 0);
            entry->first_data_ll = 0;
            entry->last_data_ll = 0;
        }
    }
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
    dict->first_data_ll = dict->last_data_ll = 0;
    dict->next = 0;

    DictEntry *cur_entry = dict;

    int in_seq = 0, in_entry = 0;
    int err = parse_tree(tree->tree, &cur_entry, &in_seq, &in_entry);
    if (err) {
        fprintf(stderr, "error parsing tree\n");
        exit(1);
    }

    DataLinkedList_to_DataPtr(dict);

    return dict;
}



void free_DataPtrs(enum data_type data_t, int nrows, int ncols, DataPtrs data) {
    if (data_t == data_i) {
        free (data.i);
    } else if (data_t == data_f) {
        free (data.f);
    } else if (data_t == data_b) {
        free (data.b);
    } else if (data_t == data_s) {
        nrows = nrows == 0 ? 1 : nrows;
        ncols = ncols == 0 ? 1 : ncols;
        for (int ri=0; ri < nrows; ri++) {
        for (int ci=0; ci < ncols; ci++) {
            free (data.s[ri*ncols + ci]);
        }
        }
        free(data.s);
    }
}

void free_arrays(Arrays *arrays) {
    Arrays *next_entry = arrays->next;
    for (Arrays *entry = arrays; entry; entry = next_entry) {
        free(entry->key);
        free_DataPtrs(entry->data_t, entry->nrows, entry->ncols, entry->data);
        free(entry);
        next_entry = entry->next;
    }
}

void free_info(DictEntry *info) {
    DictEntry *next_entry = info->next;
    for (DictEntry *entry = info; entry; entry = next_entry) {
        free(entry->key);
        free_DataLinkedList(entry->data_t, entry->first_data_ll, 1);
        free_DataPtrs(entry->data_t, entry->nrows, entry->ncols, entry->data);

        next_entry = entry->next;
        free(entry);
    }
}

void print_info_arrays(DictEntry *info, Arrays *arrays) {
    for (DictEntry *entry = info; entry; entry = entry->next) {
        printf("info '%s' type %d shape %d %d\n", entry->key, entry->data_t,
               entry->nrows, entry->ncols);
    }
    for (Arrays *entry = arrays; entry; entry = entry->next) {
        printf("array '%s' type %d shape %d %d\n", entry->key, entry->data_t,
               entry->nrows, entry->ncols);

    }
    printf("\n");
}


int extxyz_read_ll(cleri_grammar_t *kv_grammar, FILE *fp, DictEntry **info, Arrays **arrays) {
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
            props = entry->data.s[0];
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
