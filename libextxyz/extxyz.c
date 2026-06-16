#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PCRE2_CODE_UNIT_WIDTH 8
#include <pcre2.h>
#include <cleri/cleri.h>

#include "extxyz_kv_grammar.h"
#include "extxyz.h"
#include "extxyz_dispatch.h"
#include "fast_format.h"

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

// Fast path for the common per-atom float: "[+-]?int[.frac]" with no exponent
// and <= 15 significant digits. Then the integer mantissa is < 2^53 and 10^frac
// is an exact double, so the single `mant / 10^frac` is correctly rounded and
// bit-identical to strtod. Returns 1 on success; 0 (fall back to strtod) for an
// exponent, 16+ digits, or any trailing character — so high-precision and
// scientific values keep strtod's correct rounding. ~2.5x faster than strtod.
static int parse_double_fast(const char *s, double *out) {
    static const double POW10[] = {1e0,1e1,1e2,1e3,1e4,1e5,1e6,1e7,1e8,
                                   1e9,1e10,1e11,1e12,1e13,1e14,1e15};
    const char *p = s;
    int neg = 0;
    if (*p == '-') { neg = 1; p++; } else if (*p == '+') { p++; }
    unsigned long long mant = 0;
    int dig = 0, frac = 0;
    while (*p >= '0' && *p <= '9') { mant = mant*10 + (unsigned)(*p - '0'); p++; dig++; }
    if (*p == '.') {
        p++;
        while (*p >= '0' && *p <= '9') { mant = mant*10 + (unsigned)(*p - '0'); p++; dig++; frac++; }
    }
    if (*p != '\0' || dig == 0 || dig > 15 || frac > 15) {
        return 0;
    }
    double v = (double)mant / POW10[frac];
    *out = neg ? -v : v;
    return 1;
}

double atof_eEdD(char *str) {
    double v;
    if (parse_double_fast(str, &v)) {
        return v;
    }
    for (unsigned long i=0; i < strlen(str); i++) {
        if (str[i] == 'd' || str[i] == 'D') {
            str[i] = 'e';
            break;
        }
    }
    return (atof(str));
}

// Validated per-atom field parsers for the tokenizer (use_tokenizer) path. The
// regex path validates each field as a side effect of matching; the tokenizer
// just splits on whitespace, so these reject malformed tokens (return 0) that
// atoi/atof would silently accept (e.g. "NOTANUM" -> 0). Each token is
// NUL-terminated.
static int parse_int_field(const char *tok, int *out) {
    char *end;
    long v = strtol(tok, &end, 10);
    if (end == tok || *end != '\0') return 0;   // empty or trailing junk
    *out = (int) v;                              // truncates like atoi (parity)
    return 1;
}

static int parse_double_field(char *tok, double *out) {
    if (parse_double_fast(tok, out)) return 1;   // exact fast path
    // reject leads that strtod would otherwise accept (inf, nan, 0x hex)
    const char *p = tok;
    if (*p == '+' || *p == '-') p++;
    if (!((*p >= '0' && *p <= '9') || *p == '.')) return 0;
    for (char *q = tok; *q; q++) { if (*q == 'd' || *q == 'D') { *q = 'e'; break; } }
    char *end;
    double v = strtod(tok, &end);
    if (end == tok || *end != '\0') return 0;
    *out = v;
    return 1;
}

static int parse_bool_field(const char *tok, int *out) {
    // accept exactly the BOOL_RE set; value computed as the regex fill does
    // (tok[0]=='T'), so the two read modes agree bit-for-bit on valid input
    if (strcmp(tok, "T") == 0 || strcmp(tok, "F") == 0 ||
        strcmp(tok, "true") == 0 || strcmp(tok, "True") == 0 || strcmp(tok, "TRUE") == 0 ||
        strcmp(tok, "false") == 0 || strcmp(tok, "False") == 0 || strcmp(tok, "FALSE") == 0) {
        *out = (tok[0] == 'T');
        return 1;
    }
    return 0;
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

int parse_tree(cleri_node_t *node, DictEntry **cur_entry, int *in_seq, int *in_kv_pair, int *in_old_one_d, char *error_message) {
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
                        sprintf(error_message, "Failed to parse some regex as data key '%s' str '%s'\n", 
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
                    sprintf(error_message, "Failed to parse some keyword as data, key '%s' str '%s'\n", (*cur_entry)->key, str);
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
    for (cleri_node_t *child = node->children; child; child = child->next) {
        //DEBUG printf("child\n"); //DEBUG
        int err = parse_tree(child, cur_entry, in_seq, in_kv_pair, in_old_one_d, error_message);
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
                sprintf(error_message, "key %s nested list row %d number of entries in row %d inconsistent with prev %d\n", 
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

    for (cleri_node_t *child = node->children; child; child = child->next) {
        dump_tree(child, new_prefix);
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

    (void) data_t;
    DataLinkedList *next_data;
    for (DataLinkedList *data = list; data; data = next_data) {
        // Key string-freeing on each node's own type, not the entry's: on a
        // parse error the list is freed before DataLinkedList_to_data sets the
        // entry data_t, so an entry data_t of data_none would otherwise leak
        // the per-node string content. (On success the list is already NULL
        // here, so this loop is a no-op and never double-frees.)
        if (data->data_t == data_s && free_string_content) {
            free(data->data.s);
        }
        next_data = data->next;
        free(data);
    }
}


int DataLinkedList_to_data(DictEntry *dict, char *error_message) {
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
                        sprintf(error_message, "ERROR: in an array got a number type %d after a non-number %d\n",
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
                    sprintf(error_message, "ERROR: in an array got a change in type from %d to %d that cannot be promoted\n",
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


void *tree_to_dict(cleri_parse_t *tree, char *error_message) {
    //DEBUG dump_tree(tree->tree, ""); //DEBUG
    // printf("END DUMP\n");

    DictEntry *dict = (DictEntry *) malloc(sizeof(DictEntry));
    // initialize empty dict entry with no key
    init_DictEntry(dict, 0, -1);

    DictEntry *cur_entry = dict;

    int in_seq = 0, in_kv_pair = 0, in_old_one_d = 0;
    int err;
    err = parse_tree(tree->tree, &cur_entry, &in_seq, &in_kv_pair, &in_old_one_d, error_message);
    if (err) {
        sprintf(error_message, "error parsing tree\n");
        return 0;
    }

    err = DataLinkedList_to_data(dict, error_message);
    if (err) return 0;

    return dict;
}


// `width` is the entry's n_in_row: <0 means a string column is one contiguous
// fixed-width buffer (free once); >=0 is the legacy char** (free each cell —
// covers info strings, whose n_in_row is a non-negative parse-time item count).
void free_data(void *data, enum data_type data_t, int nrows, int ncols, int width) {
    if (!data) {
        return;
    }
    if (data_t == data_s && width >= 0) {
        // legacy char** : free each individually-allocated string
        nrows = nrows == 0 ? 1 : nrows;
        ncols = ncols == 0 ? 1 : ncols;
        for (int ri=0; ri < nrows; ri++) {
        for (int ci=0; ci < ncols; ci++) {
            free(((char **)data)[ri*ncols + ci]);
        }
        }
    }
    // contiguous string buffers (width>0) and all numeric data: one free
    free(data);
}


void free_dict(DictEntry *dict) {
    DictEntry *next_entry = dict->next;
    for (DictEntry *entry = dict; entry; entry = next_entry) {
        if (entry->key) {
            // fprintf(stderr, "freeing %s\n", entry->key);
            free(entry->key);
        }
        free_DataLinkedList(entry->first_data_ll, entry->data_t, 1);
        free_data(entry->data, entry->data_t, entry->nrows, entry->ncols, entry->n_in_row);

        next_entry = entry->next;
        free(entry);
    }
}

// Free the partially- or fully-built info/arrays dicts on an error path and
// NULL them out, so a failed parse neither leaks nor leaves the caller with
// dangling/half-built dictionaries it might try to read or free again.
void free_partial_dicts(DictEntry **info, DictEntry **arrays) {
    if (info && *info) { free_dict(*info); *info = 0; }
    if (arrays && *arrays) { free_dict(*arrays); *arrays = 0; }
}

// Initial bytes-per-cell for a per-atom string column. Grows on demand.
#define STR_CELL_W0 8

// Store one string field into a per-atom string column held as a single
// contiguous fixed-width buffer (numpy 'S{width}' layout). `*data` is the column
// buffer; `*n_in_row` holds the NEGATED cell width (it marks the column as
// contiguous: n_in_row < 0, width = -n_in_row). A negative sentinel is used
// because parse_tree leaves a positive n_in_row on finalized scalar info entries
// (it counts data items), so width>0 would be ambiguous. Cells are filled in
// increasing index order, so `filled` == `cell_index`. If the field doesn't fit
// the current width, the buffer is grown (calloc wider, copy the already-filled
// cells, free the old) — rare for typical short tokens. calloc zero-fills, so
// each cell stays NUL-padded (a valid C string for the writer/Fortran paths).
// Returns 0 on success, 1 on allocation failure.
static int store_str_cell(char **data, int *n_in_row, size_t total_cells,
                          size_t cell_index, size_t filled,
                          const char *pf, size_t len) {
    size_t W = (size_t)(-(*n_in_row));   // n_in_row holds -width
    if (len + 1 > W) {
        size_t newW = (len + 1 + 7) & ~(size_t)7;   // round up to a multiple of 8
        char *nb = (char *) calloc(total_cells, newW);
        if (! nb) {
            return 1;
        }
        for (size_t k = 0; k < filled; k++) {
            memcpy(nb + k*newW, *data + k*W, W);
        }
        free(*data);
        *data = nb;
        *n_in_row = -(int) newW;
        W = newW;
    }
    memcpy(*data + cell_index*W, pf, len);
    return 0;
}

void print_dict(DictEntry *dict) {
    for (DictEntry *entry = dict; entry; entry = entry->next) {
        printf("key '%s' type %d shape %d %d\n", entry->key, entry->data_t,
               entry->nrows, entry->ncols);
        /*
        printf("data: ");
        int iii = 0;
        for (int i1=0; i1 < (entry->nrows < 1 ? 1 : entry->nrows); i1++) {
        for (int i2=0; i2 < (entry->ncols < 1 ? 1 : entry->ncols); i2++) {
            switch (entry->data_t) {
                case data_i: printf("%d ", ((int *)entry->data)[iii++]);
                    break;
                case data_f: printf("%f ", ((float *)entry->data)[iii++]);
                    break;
                case data_b: printf("%c ", ((int *)entry->data)[iii++] ? 'T' : 'F');
                    break;
                case data_s: printf("%s ", ((char **)entry->data)[iii++]);
                    break;
            }
        }
        }
        printf("\n");
        */
    }
}


#define STR_INCR 1024
void strcat_realloc(char **str, unsigned long *len, char *add_str) {
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

char *read_line(char **line, unsigned long *line_len, FILE *fp) {
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

        stat = fgets(*line + *line_len - STR_INCR - 1, STR_INCR + 1, fp);
        if (!stat) {
            return 0;
        }
    }
    return *line;
}

// use_tokenizer: if non-zero, parse per-atom lines by whitespace-tokenising and
// validating each field, instead of compiling and matching a per-line PCRE2
// regex. Faster, opt-in; slightly more lenient than the grammar on numeric
// edge cases. extxyz_read_ll (below) is the regex default.
int extxyz_read_ll_opts(cleri_grammar_t *kv_grammar, FILE *fp, int *nat, DictEntry **info, DictEntry **arrays, char *comment, char *error_message, int use_tokenizer, int use_cleri) {
    char *line;
    unsigned long line_len;
    unsigned long line_len_init = 1024;

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
        sprintf(error_message, "Failed to parse int natoms from '%s'", line);
        free(line);
        return 0;
    }

    // info
    stat = read_line(&line, &line_len, fp);
    if (! stat) {
        free(line);
        return 0;
    }
    // actually parse - optionally replace line read from file with `comment` argument
    // use_cleri (default) walks the libcleri grammar; otherwise the equivalent
    // first-char-dispatch parser (extxyz_dispatch_parse) builds the same dict.
    if (use_cleri) {
        cleri_parse_t * tree;
        if (comment != NULL) {
            tree = cleri_parse(kv_grammar, comment);
        } else {
            tree = cleri_parse(kv_grammar, line);
        }
        if (! tree->is_valid) {
            sprintf(error_message, "Failed to parse string at pos %zd", tree->pos);
            cleri_parse_free(tree);
            free(line);
            return 0;
        }
        *info = tree_to_dict(tree, error_message);
        cleri_parse_free(tree);
        if (! *info) {
            sprintf(error_message, "Failed to convert tree to dict");
            free(line);
            return 0;
        }
    } else {
        *info = extxyz_dispatch_parse(comment != NULL ? comment : line, error_message);
        if (! *info) {
            free(line);
            return 0;
        }
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
            for (unsigned long i=0; i < strlen(eol); i++) {
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
    unsigned long re_str_len = 20;
    char *re_str = (char *) malloc (re_str_len * sizeof(char));
    re_str[0] = 0;
    strcat_realloc(&re_str, &re_str_len, "^\\s*");

    *arrays = (DictEntry *) 0;
    // initialised to silence a GCC -Wmaybe-uninitialized false positive; it is
    // always assigned at the top of the loop below before any use.
    DictEntry *cur_array = (DictEntry *) 0;

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
        if (! pf) {
            sprintf(error_message, "Failed to parse Properties: missing type field for property '%s' (# %d)", cur_array->key, prop_i);
            free(props);
            free(line); free(re_str);
            free_partial_dicts(info, arrays);
            return 0;
        }
        if (strlen(pf) != 1) {
            sprintf(error_message, "Failed to parse property type '%s' for property '%s' (# %d)", pf, cur_array->key, prop_i);
            free(props);
            free(line); free(re_str);
            free_partial_dicts(info, arrays);
            return 0;
        }
        char col_type = pf[0];

        // advance to col num
        pf = strtok(NULL, ":");
        if (! pf) {
            sprintf(error_message, "Failed to parse Properties: missing column count for property '%s' (# %d)", cur_array->key, prop_i);
            free(props);
            free(line); free(re_str);
            free_partial_dicts(info, arrays);
            return 0;
        }
        int col_num;
        int col_num_stat = sscanf(pf, "%d", &col_num);
        if (col_num_stat != 1) {
            sprintf(error_message, "Failed to parse int property ncolumns from '%s' for property '%s' (# %d)", pf, cur_array->key, prop_i);
            free(props);
            free(line); free(re_str);
            free_partial_dicts(info, arrays);
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
                this_re = INTEGER_RE; // "[+-]?[0-9]+";
                break;
            case 'R':
                cur_array->data_t = data_f;
                cur_array->data = malloc(((*nat)*col_num)*sizeof(double));
                this_re = FLOAT_RE; // "[+-]?(?:[0-9]+[.]?[0-9]*|\\.[0-9]+)(?:[dDeE][+-]?[0-9]+)?";
                break;
            case 'L':
                cur_array->data_t = data_b;
                cur_array->data = malloc(((*nat)*col_num)*sizeof(int));
                this_re = BOOL_RE; // "(?:[TF]|[tT]rue|[fF]alse|TRUE|FALSE)";
                break;
            case 'S':
                cur_array->data_t = data_s;
                // One contiguous fixed-width buffer for the whole column (not an
                // array of N malloc'd pointers). n_in_row carries the NEGATED
                // cell width and marks the column as contiguous (n_in_row < 0);
                // it grows on demand during the fill. calloc zero-fills so cells
                // are NUL-padded.
                cur_array->n_in_row = -STR_CELL_W0;
                cur_array->data = calloc((size_t)(*nat)*col_num, STR_CELL_W0);
                this_re = SIMPLESTRING_RE; // "\\S+";
                break;
            default:
                sprintf(error_message, "Unknown property type '%c' for property key '%s' (# %d)", col_type, cur_array->key, prop_i);
                free(props);
                free(line); free(re_str);
                // free_partial_dicts frees cur_array (incl. its data) via *arrays
                free_partial_dicts(info, arrays);
                return 0;
        }

        if (! use_tokenizer) {
            for (int ci=0; ci < col_num; ci++) {
                strcat_realloc(&re_str, &re_str_len, "(");
                strcat_realloc(&re_str, &re_str_len, this_re);
                strcat_realloc(&re_str, &re_str_len, ")");
                strcat_realloc(&re_str, &re_str_len, WHITESPACE_RE); // "\\s+");
            }
        }

        // ready to next triplet
        pf = strtok(NULL, ":");
        prop_i++;
        tot_col_num += col_num;
    }

    free(props);

    // Build/compile the per-line regex only in regex mode. In tokenizer mode
    // re/match_data stay NULL (pcre2_*_free(NULL) is a no-op) and re_str is left
    // as-is (still freed below).
    pcre2_code *re = NULL;
    pcre2_match_data *match_data = NULL;
    if (! use_tokenizer) {
        // trim off last \s+
        re_str[strlen(re_str)-3] = 0;
        // tack on to EOL
        strcat_realloc(&re_str, &re_str_len, re_at_eol);

        int pcre2_error;
        PCRE2_SIZE erroffset;
        // PCRE2_ANCHORED: our pattern starts with "^\s*" so anchoring at offset 0
        // saves the engine from probing every starting position.
        re = pcre2_compile((unsigned char *)re_str, PCRE2_ZERO_TERMINATED,
                           PCRE2_ANCHORED, &pcre2_error, &erroffset, NULL);
        if (re == NULL) {
            pcre2_get_error_message(pcre2_error, (unsigned char *)line, line_len);
            sprintf(error_message, "ERROR %s compiling pcre pattern for atoms lines offset %zu re '%s'", line, erroffset, re_str);
            free(line); free(re_str);
            free_partial_dicts(info, arrays);
            return 0;
        }
        // Try to JIT-compile. PCRE2 with JIT is typically 5-30× faster on the
        // hot pcre2_match per-atom-line loop. Silently fall through to the
        // interpreter if PCRE2 was built without JIT support — pcre2_match
        // auto-detects whether JIT is available.
        (void) pcre2_jit_compile(re, PCRE2_JIT_COMPLETE);
        match_data = pcre2_match_data_create_from_pattern(re, NULL);
    }

    // read per-atom data
    for (int li=0; li < (*nat); li++) {
        stat = read_line(&line, &line_len, fp);
        if (! stat) {
            pcre2_match_data_free(match_data); pcre2_code_free(re);
            free(line); free(re_str);
            free_partial_dicts(info, arrays);
            return 0;
        }

        if (use_tokenizer) {
            // Split the line on whitespace into exactly tot_col_num fields and
            // parse each by column type, validating numeric/bool fields.
            char *p = line;
            int field_err = 0;
            for (DictEntry *cur_array = *arrays; cur_array && !field_err; cur_array = cur_array->next) {
                int nc = cur_array->ncols;
                for (int col_i = 0; col_i < nc; col_i++) {
                    while (*p == ' ' || *p == '\t') p++;
                    if (*p == '\0' || *p == '\n' || *p == '\r') { field_err = 1; break; }
                    char *tok = p;
                    while (*p && *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r') p++;
                    size_t len = (size_t)(p - tok);
                    char sep = *p;
                    *p = '\0';
                    int ok = 1;
                    if (cur_array->data_t == data_i) {
                        ok = parse_int_field(tok, &((int *)(cur_array->data))[li*nc + col_i]);
                    } else if (cur_array->data_t == data_f) {
                        ok = parse_double_field(tok, &((double *)(cur_array->data))[li*nc + col_i]);
                    } else if (cur_array->data_t == data_b) {
                        ok = parse_bool_field(tok, &((int *)(cur_array->data))[li*nc + col_i]);
                    } else if (cur_array->data_t == data_s) {
                        size_t cell = (size_t)(li*nc + col_i);
                        if (store_str_cell((char **)&cur_array->data, &cur_array->n_in_row,
                                           (size_t)(*nat)*nc, cell, cell, tok, len)) {
                            sprintf(error_message, "ERROR: out of memory storing string on atom line %d", li);
                            pcre2_match_data_free(match_data); pcre2_code_free(re);
                            free(line); free(re_str);
                            free_partial_dicts(info, arrays);
                            return 0;
                        }
                    }
                    if (! ok) {
                        sprintf(error_message, "ERROR: invalid field '%s' for property '%s' on atom line %d", tok, cur_array->key, li);
                        pcre2_match_data_free(match_data); pcre2_code_free(re);
                        free(line); free(re_str);
                        free_partial_dicts(info, arrays);
                        return 0;
                    }
                    if (sep) p++;   // step past the separator we overwrote
                }
            }
            while (*p == ' ' || *p == '\t') p++;
            if (field_err || (*p != '\0' && *p != '\n' && *p != '\r')) {
                sprintf(error_message, "ERROR: expected %d fields on atom line %d", tot_col_num, li);
                pcre2_match_data_free(match_data); pcre2_code_free(re);
                free(line); free(re_str);
                free_partial_dicts(info, arrays);
                return 0;
            }
        } else {
        // read data with PCRE + atoi/f
        // apply PCRE
        int rc = pcre2_match(re, (unsigned char *)line, PCRE2_ZERO_TERMINATED, 0, 0, match_data, NULL);
        if (rc != tot_col_num+1) {
            if (rc < 0) {
                if (rc == PCRE2_ERROR_NOMATCH) {
                    sprintf(error_message, "ERROR: pcre2 regexp got NOMATCH on atom line %d", li);
                } else {
                    sprintf(error_message, "ERROR: pcre2 regexp got error %d on atom line %d", rc, li);
                }
            } else if (rc == 0) {
                sprintf(error_message, "ERROR: pcre2 regexp got match_data not big enough (should never happen) on atom line %d", li);
            } else {
                sprintf(error_message, "ERROR: pcre2 regexp failed on atom line %d at group %d", li, rc-1);
            }
            pcre2_match_data_free(match_data); pcre2_code_free(re);
            free(line); free(re_str);
            free_partial_dicts(info, arrays);
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
                    // field bounds from the PCRE2 capture (pf is NUL-terminated
                    // at line[ovector[2*field_i+1]] above)
                    size_t len = (size_t)(ovector[2*field_i+1] - ovector[2*field_i]);
                    size_t cell = (size_t)(li*nc + col_i);
                    if (store_str_cell((char **)&cur_array->data, &cur_array->n_in_row,
                                       (size_t)(*nat)*nc, cell, cell, pf, len)) {
                        sprintf(error_message, "ERROR: out of memory storing string on atom line %d", li);
                        pcre2_match_data_free(match_data); pcre2_code_free(re);
                        free(line); free(re_str);
                        free_partial_dicts(info, arrays);
                        return 0;
                    }
                }
                field_i++;
            }
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

// Backward-compatible reader: per-atom lines parsed with the PCRE2 regex,
// comment line parsed with the libcleri grammar.
int extxyz_read_ll(cleri_grammar_t *kv_grammar, FILE *fp, int *nat, DictEntry **info, DictEntry **arrays, char *comment, char *error_message) {
    return extxyz_read_ll_opts(kv_grammar, fp, nat, info, arrays, comment, error_message, 0, 1);
}

////////////////////////////////////////////////////////////////////////////////////////////////////
// WRITING CODE
////////////////////////////////////////////////////////////////////////////////////////////////////

char *quoted(char *data) {
    // count escaped and special chars
    int have_special=0;
    int n_escape=0;
    for (char *c=data; *c; c++) {
        // escape double quote and backslash
        n_escape += ((*c == '"' || *c == '\\' || *c == '\n') ? 1 : 0);
        // count any special chars
        have_special |= (*c == ' ' || *c == '=' || *c == '"' || *c == ',' || *c == '[' ||
                         *c == ']' || *c == '{' || *c == '}' || *c == '\\' || *c == '\n');
    }

    // copy, quoting/escaping as needed
    int len = 1 + (have_special ? 2 : 0) + strlen(data) + n_escape;
    char *str = (char *)malloc(len * sizeof(char));
    int c_o=0;
    if (have_special) {
        str[c_o++] = '"';
    }
    for (char *c=data; *c; c++, c_o++) {
        if (*c == '\n') {
            str[c_o] = '\\';
            str[c_o+1] = 'n';
            c_o++;
        } else if (*c == '\\' || *c == '"') {
            str[c_o] = '\\';
            str[c_o+1] = *c;
            c_o++;
        } else {
            str[c_o] = *c;
        }
    }
    if (have_special) {
        str[c_o++] = '"';
    }
    str[c_o] = 0;

    return str;
}

#define IFB_STR_LEN 128
int concat_elem(char **str, unsigned long *str_len, enum data_type data_t, void *data, int offset) {
    char field_str[IFB_STR_LEN], *field_str_ptr;
    field_str_ptr = field_str;
    switch (data_t) {
        case data_i:
            sprintf(field_str, INTEGER_FMT, ((int *)data)[offset]);
            break;
        case data_f:
            sprintf(field_str, FLOAT_FMT, ((double *)data)[offset]);
            break;
        case data_b:
            sprintf(field_str, STRING_FMT, ((int *)data)[offset] ? "T" : "F");
            break;
        case data_s:
            field_str_ptr = quoted(((char **)data)[offset]);
            break;
        default:
            return 1;
    }

    if (data_t != data_s) {
        // strip leading whitespace
        for(; *field_str_ptr && (field_str_ptr[0] == ' ' ||
                                 field_str_ptr[0] == '\t' ||
                                 field_str_ptr[0] == '\n'); field_str_ptr++);
    }
    strcat_realloc(str, str_len, field_str_ptr);
    if (data_t == data_s) {
        free(field_str_ptr);
    }

    return 0;
}

int concat_entry(char **str, unsigned long *str_len, DictEntry *entry, int old_style_3_3) {
    if (entry->nrows == 0) {
        // scalar or vector
        if (entry->ncols == 0) {
            //scalar
            int err_stat = concat_elem(str, str_len, entry->data_t, entry->data, 0);
            return err_stat;
        } else {
            //vector
            strcat_realloc(str, str_len, "[");
            for (int i_col=0; i_col < entry->ncols; i_col++) {
                int err_stat = concat_elem(str, str_len, entry->data_t, entry->data, i_col);
                if (err_stat) {
                    return err_stat;
                }
                if (i_col < entry->ncols-1) {
                    strcat_realloc(str, str_len, ", ");
                }
            }
            strcat_realloc(str, str_len, "]");
        }
    } else {
        // matrix
        if (old_style_3_3) {
            // only certain shapes and types are valid as old style matrices
            if ((entry->nrows != 3 || entry->ncols != 3)) {
                return 2;
            }
            if (entry->data_t != data_i && entry->data_t != data_f && entry->data_t != data_b) {
                return 3;
            }
        }
        // before all rows
        if (old_style_3_3) {
            strcat_realloc(str, str_len, "\"");
        } else {
            strcat_realloc(str, str_len, "[");
        }
        for (int i_row=0; i_row < entry->nrows; i_row++) {
            // start of row
            if (!old_style_3_3) {
                strcat_realloc(str, str_len, "[");
            }
            // do data
            for (int i_col=0; i_col < entry->ncols; i_col++) {
                int err_stat;
                if (old_style_3_3) {
                    // transpose iff old style 3x3
                    err_stat = concat_elem(str, str_len, entry->data_t, entry->data, (i_col*entry->nrows)+i_row);
                } else{
                    err_stat = concat_elem(str, str_len, entry->data_t, entry->data, (i_row*entry->ncols)+i_col);
                }
                if (err_stat) {
                    return err_stat;
                }
                if (i_col < entry->ncols-1) {
                    if (old_style_3_3) {
                        strcat_realloc(str, str_len, " ");
                    } else {
                        strcat_realloc(str, str_len, ", ");
                    }
                }
            }
            // after a row
            if (i_row < entry->nrows-1) {
                if (old_style_3_3) {
                    strcat_realloc(str, str_len, " ");
                } else {
                    strcat_realloc(str, str_len, "], ");
                }
            } else if (!old_style_3_3) {
                strcat_realloc(str, str_len, "]");
            }
        }
        // after all rows
        if (old_style_3_3) {
            strcat_realloc(str, str_len, "\"");
        } else {
            strcat_realloc(str, str_len, "]");
        }
    }
    return 0;
}

// Write with caller-supplied per-atom column formats. Any of fmt_i/fmt_f/
// fmt_b/fmt_s may be NULL to use the compiled-in default. The formats apply to
// the per-atom data columns only (matching the pure-Python writer's
// format_dict); info-line values keep the default formatting. fmt_f must
// consume a double, fmt_i an int, fmt_b/fmt_s a char* ("T"/"F" or the string).
int extxyz_write_ll_fmt(FILE *fp, int nat, DictEntry *info, DictEntry *arrays,
                        const char *fmt_i, const char *fmt_f,
                        const char *fmt_b, const char *fmt_s) {
    const char *FMT_I = fmt_i ? fmt_i : INTEGER_FMT;
    const char *FMT_F = fmt_f ? fmt_f : FLOAT_FMT;
    const char *FMT_B = fmt_b ? fmt_b : BOOL_FMT;
    const char *FMT_S = fmt_s ? fmt_s : STRING_FMT;
    // The default "%16.8f" has a fast exact formatter; custom float formats
    // (format_dict, #22) keep using snprintf via WB_FMT.
    const int f_default = (fmt_f == NULL);

    fprintf(fp, "%d\n", nat);

    // Write info

    unsigned long entry_str_len=100;
    char *entry_str = (char *)malloc(entry_str_len * sizeof(char));

    for (DictEntry *entry=info; entry; entry = entry->next) {
        // should this be necessary?
        if (! strcmp(entry->key, "Properties")) {
            continue;
        }

        entry_str[0] = 0;
        // key
        char *quoted_key = quoted(entry->key);
        strcat_realloc(&entry_str, &entry_str_len, quoted_key);
        free(quoted_key);

        // =
        strcat_realloc(&entry_str, &entry_str_len, "=");

        // value
        // (only) Lattice is always written as old style 3x3
        int old_style_3_3 = !strcmp(entry->key, "Lattice");
        int err_stat = concat_entry(&entry_str, &entry_str_len, entry, old_style_3_3);
        if (err_stat) { free(entry_str); return err_stat; }

        fprintf(fp, "%s", entry_str);
        if (entry->next) {
            fprintf(fp, " ");
        }
    }
    free (entry_str);

    // create and write Properties

    unsigned long properties_str_len=100;
    char *properties_str = (char *)malloc(properties_str_len * sizeof(char));
    properties_str[0] = 0;
    for (DictEntry *entry=arrays; entry; entry = entry->next) {
        strcat_realloc(&properties_str, &properties_str_len, entry->key);
        strcat_realloc(&properties_str, &properties_str_len, ":");
        switch (entry->data_t) {
            case data_i: strcat_realloc(&properties_str, &properties_str_len, "I");
                break;
            case data_f: strcat_realloc(&properties_str, &properties_str_len, "R");
                break;
            case data_b: strcat_realloc(&properties_str, &properties_str_len, "L");
                break;
            case data_s: strcat_realloc(&properties_str, &properties_str_len, "S");
                break;
            default:
                free (properties_str);
                return 5;
        }
        strcat_realloc(&properties_str, &properties_str_len, ":");
        char col_num_str[IFB_STR_LEN];
        sprintf(col_num_str, "%d", (entry->nrows == 0 ? 1 : entry->ncols));
        strcat_realloc(&properties_str, &properties_str_len, col_num_str);
        if (entry->next) {
            strcat_realloc(&properties_str, &properties_str_len, ":");
        }
    }

    // quote in case there are special characters in keys
    char *quoted_properties_str = quoted(properties_str);
    fprintf(fp, " Properties=%s\n", quoted_properties_str);
    free(quoted_properties_str);
    free(properties_str);

    // write per-atom data. Build each line in a growable memory buffer with
    // snprintf and fwrite it in blocks, instead of one (FILE-locked) fprintf per
    // value — same output bytes, fewer locked stdio calls. Flush at line
    // boundaries once the buffer passes WBUF_FLUSH so a line is never split.
    size_t wbuf_cap = 1u << 16, wbuf_n = 0;
    const size_t WBUF_FLUSH = 1u << 15;
    char *wbuf = (char *) malloc(wbuf_cap);
    if (! wbuf) { return 7; }
    // append `fmt`-formatted `val`, growing the buffer (and re-formatting) only
    // if it didn't fit — for a flushed buffer it almost always fits first time.
    #define WB_FMT(fmt, val) do { \
        int _l = snprintf(wbuf + wbuf_n, wbuf_cap - wbuf_n, (fmt), (val)); \
        if (_l < 0) { free(wbuf); return 7; } \
        if ((size_t)_l >= wbuf_cap - wbuf_n) { \
            while (wbuf_n + (size_t)_l + 1 > wbuf_cap) wbuf_cap *= 2; \
            char *_nb = (char *) realloc(wbuf, wbuf_cap); \
            if (! _nb) { free(wbuf); return 7; } \
            wbuf = _nb; \
            snprintf(wbuf + wbuf_n, wbuf_cap - wbuf_n, (fmt), (val)); \
        } \
        wbuf_n += (size_t)_l; \
    } while (0)
    #define WB_CH(c) do { \
        if (wbuf_n + 1 > wbuf_cap) { \
            wbuf_cap *= 2; \
            char *_nb = (char *) realloc(wbuf, wbuf_cap); \
            if (! _nb) { free(wbuf); return 7; } \
            wbuf = _nb; \
        } \
        wbuf[wbuf_n++] = (c); \
    } while (0)
    // append a default-formatted ("%16.8f") double via the fast exact formatter,
    // reserving its worst-case width first.
    #define WB_FLOAT(val) do { \
        if (wbuf_cap - wbuf_n < FMT_F16_8_BUFSIZE) { \
            while (wbuf_n + FMT_F16_8_BUFSIZE > wbuf_cap) wbuf_cap *= 2; \
            char *_nb = (char *) realloc(wbuf, wbuf_cap); \
            if (! _nb) { free(wbuf); return 7; } \
            wbuf = _nb; \
        } \
        wbuf_n += (size_t)fmt_default_f16_8(wbuf + wbuf_n, (val)); \
    } while (0)

    for (int i_at=0; i_at < nat; i_at++) {
        for (DictEntry *entry = arrays; entry; entry = entry->next) {
            int ncols = (entry->nrows == 0) ? 1 : entry->ncols;
            switch(entry->data_t) {
                case data_i:
                    for (int i_col=0; i_col < ncols; i_col++) {
                        WB_FMT(FMT_I, ((int *)(entry->data))[i_at*ncols+i_col]);
                        if (i_col < ncols-1) { WB_CH(' '); }
                    }
                    break;
                case data_f:
                    for (int i_col=0; i_col < ncols; i_col++) {
                        double _v = ((double *)(entry->data))[i_at*ncols+i_col];
                        if (f_default) { WB_FLOAT(_v); }
                        else { WB_FMT(FMT_F, _v); }
                        if (i_col < ncols-1) { WB_CH(' '); }
                    }
                    break;
                case data_b:
                    for (int i_col=0; i_col < ncols; i_col++) {
                        WB_FMT(FMT_B, ((int *)(entry->data))[i_at*ncols+i_col] ? "T" : "F");
                        if (i_col < ncols-1) { WB_CH(' '); }
                    }
                    break;
                case data_s:
                    for (int i_col=0; i_col < ncols; i_col++) {
                        // assuming simple string, no need for quotes.
                        // n_in_row>0: contiguous fixed-width buffer (read path /
                        // Fortran); 0: legacy char** (Python write via py_to_c_dict)
                        const char *s = (entry->n_in_row < 0)
                            ? (const char *)entry->data + (size_t)(i_at*ncols+i_col)*(-entry->n_in_row)
                            : ((char **)(entry->data))[i_at*ncols+i_col];
                        WB_FMT(FMT_S, s);
                        if (i_col < ncols-1) { WB_CH(' '); }
                    }
                    break;
                default:
                    free(wbuf);
                    return 6;
            }
            if (entry->next) { WB_CH(' '); WB_CH(' '); WB_CH(' '); }
        }
        WB_CH('\n');
        if (wbuf_n >= WBUF_FLUSH) { fwrite(wbuf, 1, wbuf_n, fp); wbuf_n = 0; }
    }
    if (wbuf_n) { fwrite(wbuf, 1, wbuf_n, fp); }
    free(wbuf);
    #undef WB_FMT
    #undef WB_CH
    #undef WB_FLOAT

    return 0;
}

// Backward-compatible writer: default per-atom column formats.
int extxyz_write_ll(FILE *fp, int nat, DictEntry *info, DictEntry *arrays) {
    return extxyz_write_ll_fmt(fp, nat, info, arrays, NULL, NULL, NULL, NULL);
}

// Utility function to allocate memory from Fortran

void* extxyz_malloc(size_t n_bytes) {
    void *res = malloc(n_bytes);
    // fprintf(stderr, "allocated %ld bytes at %x\n", n_bytes, res);
    return res;
}

// stdio thunks called via ctypes from Python. Routing fopen/fclose/ftell/fseek
// through this DLL guarantees the FILE* lives in the same C runtime that
// extxyz_read_ll/extxyz_write_ll use, avoiding CRT-mismatch crashes on Windows.

FILE *extxyz_fopen(const char *filename, const char *mode) {
    return fopen(filename, mode);
}

int extxyz_fclose(FILE *fp) {
    return fclose(fp);
}

long extxyz_ftell(FILE *fp) {
    return ftell(fp);
}

int extxyz_fseek(FILE *fp, long offset, int whence) {
    return fseek(fp, offset, whence);
}
