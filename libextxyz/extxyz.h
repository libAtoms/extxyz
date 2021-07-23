/* interface for the the low-level C wrapper around libcleri parsed extxyz comment lines.

   int extxyz_read_ll(kv_grammar, fp, nat, info, arrays)
   Parameters:
     cleri_grammar_t *kv_grammar: grammar, passed in so it does not have to be compiled in every time.
        calling routine should compile once and save indefinitely
     FILE *fp: file pointer to object to be read from, positioned at start of natoms line
     int *nat: storage for number of atoms
     DictEntry **info: pointer to allocated storage for info dict, will return pointer to first entry in linked list
     DictEntry **arrays: pointer to allocated storage for arrays dict, will return pointer to first entry in linked list
   Returns
     int 0 for failure and 1 for success.

   Usage:
      compile grammar (once)
      allocate int nat, DictEntry *info and arrays 
      pass in pointers to those 3 quantities
      test return value for error (info should have been printed to stderr if error)
      use info and arrays to construct output data structures
      call free_fict(dict) for each of them to free C-allocated memory

   DictEntry data type:
    char *key - null-terminated C string with entry key
    void *data - pointer to C-allocated data
        int: int *
        float: double *
        bool: int *
        string: char **, each element points to a malloc'ed null-terminated C string (char *)
    enum data_type data_t: indicator of stored data type
    int nrows, ncols: dimension of data.  
        nrows == ncols == 0 is a scalar
        nrows == 0, ncols > 0 is a vector
        nrows > 0, ncols > 0 is a matrix

    first_data_ll, last_data_ll, and n_in_row are for internal use only
*/

enum data_type {data_none, data_i, data_f, data_b, data_s};

// for internal use only
typedef struct data_list_struct {
    union {
        int i;
        double f;
        char *s;
        int b;
    } data;

    enum data_type data_t;

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
int extxyz_write_ll(FILE *fp, int nat, DictEntry *info, DictEntry *arrays);
void* extxyz_malloc(size_t nbytes);