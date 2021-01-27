enum data_type {data_i, data_f, data_b, data_s};

typedef struct data_list_struct {
    union {
        int i;
        double f;
        char *s;
        int b;
    } data;

    struct data_list_struct *next;
} DataLinkedList;

typedef union data_pointers {
    int *i;
    double *f;
    char **s;
    int *b;
} DataPtrs;

typedef struct arrays_struct {
    char *key;

    DataPtrs data;

    enum data_type data_t;
    int nrows, ncols;

    struct arrays_struct *next;
} Arrays;

typedef struct dict_entry_struct {
    char *key;

    DataLinkedList *first_data_ll, *last_data_ll;
    DataPtrs data;
    enum data_type data_t; 
    int nrows, ncols, n_in_row;

    struct dict_entry_struct *next;
} DictEntry;

void print_info_arrays(DictEntry *info, Arrays *arrays);
void free_info(DictEntry *info);
void free_arrays(Arrays *arrays);
int extxyz_read_ll(cleri_grammar_t *kv_grammar, FILE *fp, DictEntry **info, Arrays **arrays);
