enum data_type {data_none, data_i, data_f, data_b, data_s};

// for internal use only
typedef struct data_list_struct {
    union {
        int i;
        double f;
        char *s;
        int b;
    } data;

    struct data_list_struct *next;
} DataLinkedList;

typedef struct dict_entry_struct {
    char *key;

    void *data;
    enum data_type data_t; 
    int nrows, ncols;

    struct dict_entry_struct *next;

    // for internal use only
    DataLinkedList *first_data_ll, *last_data_ll;
    int n_in_row;
} DictEntry;

void print_dict(DictEntry *dict);
void free_dict(DictEntry *dict);
int extxyz_read_ll(cleri_grammar_t *kv_grammar, FILE *fp, int *nat, DictEntry **info, DictEntry **arrays);
