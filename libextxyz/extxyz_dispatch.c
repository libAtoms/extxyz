/* First-char-dispatch parser for the extended-XYZ comment line.
 *
 * Grammar-faithful: reproduces the pyleri/libcleri accepted language and
 * produces a DictEntry list identical to tree_to_dict(), but dispatches each
 * value on its first non-space character so only the relevant val_item
 * alternative(s) are tried instead of libcleri walking the whole ordered
 * Choice, and folds parse + marshalling into one pass.
 *
 * Token extents are validated with the EXACT grammar PCRE2 patterns (the same
 * INTEGER_RE/FLOAT_RE/BOOL_RE the generated grammar uses), so the accepted
 * language matches by construction. Output parity is then guaranteed by reusing
 * the real finalize (DataLinkedList_to_data) + helpers from extxyz.c.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define PCRE2_CODE_UNIT_WIDTH 8
#include <pcre2.h>

#include <cleri/cleri.h>         /* for cleri_grammar_t referenced in extxyz.h */
#include "extxyz.h"
#include "extxyz_kv_grammar.h"   /* INTEGER_RE, FLOAT_RE, BOOL_RE */
#include "extxyz_dispatch.h"

/* ---- reused from extxyz.c (non-static) ---- */
extern void init_DictEntry(DictEntry *entry, const char *key, const int key_len);
extern int  DataLinkedList_to_data(DictEntry *dict, char *error_message);
extern double atof_eEdD(char *str);
extern void unquote(char *str);

/* ---- regex strings the generated grammar uses (from grammar/extxyz_kv_grammar.py) ---- */
#define BARESTRING_RE "(?:[^\\s=\",}{\\]\\[\\\\]|(?:\\\\[\\s=\",}{\\]\\[\\\\]))+"
#define DQ_RE "(\")(?:(?=(\\\\?))\\2.)*?\\1"
#define CB_RE "{(?:[^{}]|\\\\[{}])*(?<!\\\\)}"
#define SB_RE "\\[(?:[^\\[\\]]|\\\\[\\[\\]])*(?<!\\\\)\\]"
#define PROP_RE "([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+)(:([a-zA-Z_][a-zA-Z_0-9]*):([RILS]):([0-9]+))*"

enum { RX_INT, RX_FLOAT, RX_BOOL, RX_BARE, RX_DQ, RX_CB, RX_SB, RX_PROP, NRX };
static pcre2_code *g_rx[NRX];
static const char *g_rx_src[NRX] = { INTEGER_RE, FLOAT_RE, BOOL_RE, BARESTRING_RE, DQ_RE, CB_RE, SB_RE, PROP_RE };
static int g_initialized = 0;

void extxyz_dispatch_init(void) {
    if (g_initialized) return;
    int err; PCRE2_SIZE eo;
    for (int i = 0; i < NRX; i++) {
        g_rx[i] = pcre2_compile((PCRE2_SPTR)g_rx_src[i], PCRE2_ZERO_TERMINATED, 0, &err, &eo, NULL);
        if (!g_rx[i]) { fprintf(stderr, "extxyz_dispatch: regex %d compile fail at %zu\n", i, eo); exit(2); }
        pcre2_jit_compile(g_rx[i], PCRE2_JIT_COMPLETE);
    }
    g_initialized = 1;
}

void extxyz_dispatch_free(void) {
    if (!g_initialized) return;
    for (int i = 0; i < NRX; i++) { pcre2_code_free(g_rx[i]); g_rx[i] = NULL; }
    g_initialized = 0;
}

/* anchored match of pattern i at s+pos; returns match length, or -1 if no match. */
static int rmatch(int i, const char *s, size_t len, size_t pos) {
    pcre2_match_data *md = pcre2_match_data_create_from_pattern(g_rx[i], NULL);
    int rc = pcre2_match(g_rx[i], (PCRE2_SPTR)s, len, pos, PCRE2_ANCHORED, md, NULL);
    int out = -1;
    if (rc >= 0) {
        PCRE2_SIZE *ov = pcre2_get_ovector_pointer(md);
        out = (int)(ov[1] - ov[0]);
    }
    pcre2_match_data_free(md);
    return out;
}

/* ---- DataLinkedList append (mirrors parse_tree) ---- */
static void append_item(DictEntry *e, enum data_type t, int iv, double fv, int bv, char *sv) {
    DataLinkedList *d = (DataLinkedList *)malloc(sizeof(DataLinkedList));
    d->next = 0; d->data_t = t;
    if (t == data_i) d->data.i = iv;
    else if (t == data_f) d->data.f = fv;
    else if (t == data_b) d->data.b = bv;
    else d->data.s = sv;
    if (!e->first_data_ll) e->first_data_ll = d; else e->last_data_ll->next = d;
    e->last_data_ll = d;
}

/* dup [pos,pos+n) into a fresh NUL-terminated buffer */
static char *dupn(const char *s, size_t pos, int n) {
    char *r = (char *)malloc(n + 1);
    memcpy(r, s + pos, n); r[n] = 0; return r;
}

static int is_ws(char c) { return c==' '||c=='\t'||c=='\n'||c=='\r'||c=='\f'||c=='\v'; }
static void skip_ws(const char *s, size_t len, size_t *pos) { while (*pos<len && is_ws(s[*pos])) (*pos)++; }

/* store a scalar number/bool/bare token already typed */
static void store_scalar(DictEntry *e, int which, const char *s, size_t pos, int n) {
    char *tok = dupn(s, pos, n);
    if (which==RX_INT)      append_item(e, data_i, atoi(tok), 0, 0, 0), free(tok);
    else if (which==RX_FLOAT) append_item(e, data_f, 0, atof_eEdD(tok), 0, 0), free(tok);
    else if (which==RX_BOOL)  append_item(e, data_b, 0, 0, (tok[0]=='T'||tok[0]=='t'), 0), free(tok);
    else append_item(e, data_s, 0, 0, 0, tok); /* bare string: keep tok */
}

/* Consume the separator before a non-first element. Returns 1 if a valid
   separator was found (positioned at the next element), 0 to fail.
   require_comma: new-style "[...]" arrays use comma delimiters (pyleri List);
   old-style "..."/{...} containers also accept whitespace (Repeat). A trailing
   comma immediately before `close` is rejected (matches the grammar). */
static int consume_sep(const char *s, size_t len, size_t *pp, char close, int require_comma) {
    size_t p = *pp;
    if (p<len && s[p]==',') {
        p++; skip_ws(s,len,&p);
        if (p>=len || s[p]==close) return 0;   /* trailing comma */
    } else if (require_comma) {
        return 0;                               /* bracket array needs a comma */
    }
    /* else: whitespace already skipped by caller -> whitespace separator */
    *pp = p;
    return 1;
}

/* Try to parse a container body (after the opening quote/bracket) of numbers/
   bools. Returns body element count and sets *type, or -1 if it isn't a clean
   numeric/bool list. require_comma distinguishes "[...]" (commas) from old
   "..."/{...} containers (whitespace or commas). */
static int parse_old_body(const char *s, size_t len, size_t *pp, char close,
                          DictEntry *e, enum data_type *type, int require_comma) {
    size_t p = *pp; int count = 0; enum data_type t = data_none;
    for (;;) {
        skip_ws(s, len, &p);
        if (p<len && s[p]==close) break;
        if (p>=len) return -1;
        if (count>0 && !consume_sep(s, len, &p, close, require_comma)) return -1;
        /* dispatch the element on its first char to avoid trying every type */
        char ec=s[p]; enum data_type et; int n;
        if ((ec>='0'&&ec<='9')||ec=='+'||ec=='-'||ec=='.') {
            int ni=rmatch(RX_INT,s,len,p), nf=rmatch(RX_FLOAT,s,len,p);
            if (ni>0 && ni>=nf) { et=data_i; n=ni; }
            else if (nf>0)      { et=data_f; n=nf; }
            else return -1;
        } else {
            int nb=rmatch(RX_BOOL,s,len,p);
            if (nb>0) { et=data_b; n=nb; }
            else return -1; /* not numeric/bool -> caller falls back to string */
        }
        /* homogeneity with promotion: i/f mix -> f; anything else must match */
        if (t==data_none) t=et;
        else if ((t==data_i||t==data_f)&&(et==data_i||et==data_f)) { if (et==data_f||t==data_f) t=data_f; }
        else if (t!=et) return -1;
        store_scalar(e, et==data_i?RX_INT:et==data_f?RX_FLOAT:RX_BOOL, s, p, n);
        p += n; count++;
    }
    if (p>=len || s[p]!=close) return -1;
    p++; /* consume close */
    *pp = p; *type = t;
    return count;
}

/* parse a list of r_string elements until `close` (one_d_array_s / strings_sp).
   Returns count, or -1 if an element isn't a valid string or close is missing.
   require_comma as in parse_old_body. */
static int parse_string_list(const char *s, size_t len, size_t *pp, char close,
                             DictEntry *e, int require_comma) {
    size_t p=*pp; int count=0;
    for (;;) {
        skip_ws(s,len,&p);
        if (p<len && s[p]==close) break;
        if (p>=len) return -1;
        if (count>0 && !consume_sep(s, len, &p, close, require_comma)) return -1;
        char c=s[p]; int n; int which=-1;
        if (c=='"') which=RX_DQ; else if (c=='{') which=RX_CB; else if (c=='[') which=RX_SB;
        if (which>=0) { n=rmatch(which,s,len,p); }
        else { n=rmatch(RX_BARE,s,len,p); }
        if (n<=0) return -1;
        char *tok=dupn(s,p,n); if (which>=0) unquote(tok);
        append_item(e,data_s,0,0,0,tok);
        p+=n; count++;
    }
    if (p>=len || s[p]!=close) return -1;
    p++; *pp=p; return count;
}

/* free any partial data list on an entry (used on old-container backtrack) */
static void reset_entry_data(DictEntry *e) {
    DataLinkedList *d=e->first_data_ll, *nx;
    while (d){ nx=d->next; if (d->data_t==data_s) free(d->data.s); free(d); d=nx; }
    e->first_data_ll=e->last_data_ll=0; e->n_in_row=0; e->nrows=e->ncols=0;
}

/* parse one value into entry e; returns end pos or (size_t)-1 on failure */
static size_t parse_value(const char *s, size_t len, size_t pos, DictEntry *e) {
    skip_ws(s, len, &pos);
    if (pos>=len) return (size_t)-1;
    char c = s[pos];

    /* --- new-style bracket array [...] / [[...]] (comma-delimited) --- */
    if (c=='[') {
        size_t probe=pos+1; skip_ws(s,len,&probe);
        int two_d = (probe<len && s[probe]=='[');
        size_t p=pos+1;
        if (two_d) {
            int ncols=-1, nrows=0;
            for (;;){
                skip_ws(s,len,&p);
                if (p<len && s[p]==']'){p++;break;}
                if (p>=len) return (size_t)-1;
                if (nrows>0 && !consume_sep(s,len,&p,']',1)) return (size_t)-1;
                if (p>=len || s[p]!='[') return (size_t)-1;
                size_t rs=p+1, rp=p+1; enum data_type t;
                int n=parse_old_body(s,len,&rp,']',e,&t,1);
                if (n<0) { /* string row (one_d_array_s) */
                    rp=rs; n=parse_string_list(s,len,&rp,']',e,1);
                    if (n<0) return (size_t)-1;
                }
                p=rp;
                if (ncols<0) ncols=n; else if (ncols!=n) return (size_t)-1;
                nrows++;
            }
            e->nrows=nrows; e->ncols=ncols;
        } else {
            enum data_type t; int n=parse_old_body(s,len,&p,']',e,&t,1);
            if (n<0) {  /* one_d_array_s: all-string [...]; else sb-string scalar */
                reset_entry_data(e);
                size_t ps=pos+1; int sc=parse_string_list(s,len,&ps,']',e,1);
                if (sc>0) { e->nrows=0; e->ncols=sc; return ps; }
                reset_entry_data(e);
                int sl=rmatch(RX_SB,s,len,pos);
                if (sl<0) return (size_t)-1;
                char *tok=dupn(s,pos,sl); unquote(tok);
                append_item(e,data_s,0,0,0,tok); e->nrows=e->ncols=0;
                return pos+sl;
            }
            e->nrows=0; e->ncols=n;
        }
        return p;
    }

    /* --- old-style container "..." {...}  OR quoted string --- */
    if (c=='"' || c=='\'' || c=='{') {
        char close = (c=='{') ? '}' : c;
        size_t p=pos+1; enum data_type t;
        int n=parse_old_body(s,len,&p,close,e,&t,0);
        if (n>=0) {
            /* old-array shape rules */
            if (n==1) { e->nrows=0; e->ncols=0; }            /* single -> scalar */
            else if (n==9) { e->nrows=-3; e->ncols=-3; }     /* 9 -> 3x3 transpose */
            else { e->nrows=0; e->ncols=n; }
            return p;
        }
        /* {…} also allows a string list (old_one_d_array strings branch) */
        if (c=='{') {
            reset_entry_data(e);
            size_t ps=pos+1; int sc=parse_string_list(s,len,&ps,'}',e,0);
            if (sc>0) {
                if (sc==1){e->nrows=0;e->ncols=0;} else if (sc==9){e->nrows=-3;e->ncols=-3;}
                else {e->nrows=0;e->ncols=sc;}
                return ps;
            }
            reset_entry_data(e);
        }
        /* backtrack -> quoted string. Single quotes are not a string container. */
        reset_entry_data(e);
        if (c=='\'') return (size_t)-1;
        int which = (c=='"') ? RX_DQ : RX_CB;
        int sl=rmatch(which,s,len,pos);
        if (sl<0) return (size_t)-1;
        char *tok=dupn(s,pos,sl); unquote(tok);
        append_item(e,data_s,0,0,0,tok); e->nrows=e->ncols=0;
        return pos+sl;
    }

    /* --- scalar: most_greedy over {int,float,bool,bare-string} --- */
    int ni=rmatch(RX_INT,s,len,pos), nf=rmatch(RX_FLOAT,s,len,pos);
    int nb=rmatch(RX_BOOL,s,len,pos), ns=rmatch(RX_BARE,s,len,pos);
    int best=-1, which=-1;
    if (ni>best){best=ni;which=RX_INT;}
    if (nf>best){best=nf;which=RX_FLOAT;}
    if (nb>best){best=nb;which=RX_BOOL;}
    if (ns>best){best=ns;which=RX_BARE;}
    if (best<=0) return (size_t)-1;
    store_scalar(e, which, s, pos, best);
    e->nrows=0; e->ncols=0;
    return pos+best;
}

/* parse a key into *keyout (NUL-terminated, unquoted); returns end pos or -1 */
static size_t parse_key(const char *s, size_t len, size_t pos, char **keyout, int *keylen) {
    skip_ws(s,len,&pos);
    if (pos>=len) return (size_t)-1;
    char c=s[pos];
    if (c=='"'||c=='{'||c=='[') {
        int which=(c=='"')?RX_DQ:(c=='{')?RX_CB:RX_SB;
        int n=rmatch(which,s,len,pos); if (n<0) return (size_t)-1;
        char *k=dupn(s,pos,n); unquote(k); *keyout=k; *keylen=(int)strlen(k);
        return pos+n;
    }
    int n=rmatch(RX_BARE,s,len,pos); if (n<0) return (size_t)-1;
    *keyout=dupn(s,pos,n); *keylen=n;
    return pos+n;
}

static void set_parse_error(char *error_message, size_t pos) {
    if (error_message) sprintf(error_message, "Failed to parse string at pos %zd", pos);
}

/* Public: parse a comment line, returns DictEntry head or NULL on reject. */
DictEntry *extxyz_dispatch_parse(const char *s, char *error_message) {
    extxyz_dispatch_init();   /* idempotent; no-op once compiled */
    size_t len=strlen(s), pos=0;
    DictEntry *dict=(DictEntry*)malloc(sizeof(DictEntry));
    init_DictEntry(dict,0,-1);
    DictEntry *cur=dict;

    skip_ws(s,len,&pos);
    while (pos<len) {
        /* try Properties=<propstr> first (all_kv_pair order) */
        int handled=0;
        if ((len-pos)>=10 && strncasecmp(s+pos,"properties",10)==0) {
            size_t p=pos+10;
            if (p>=len || !(isalnum((unsigned char)s[p])||s[p]=='_')) { /* keyword \b */
                skip_ws(s,len,&p);
                if (p<len && s[p]=='='){ p++; skip_ws(s,len,&p);
                    int pl=rmatch(RX_PROP,s,len,p);
                    if (pl>0) {
                        if (cur->key){ DictEntry*ne=malloc(sizeof(DictEntry)); cur->next=ne; cur=ne; }
                        init_DictEntry(cur,"Properties",10);
                        char *v=dupn(s,p,pl); append_item(cur,data_s,0,0,0,v);
                        cur->nrows=cur->ncols=0;
                        pos=p+pl; handled=1;
                    }
                }
            }
        }
        if (!handled) {
            char *key; int klen;
            size_t kp=parse_key(s,len,pos,&key,&klen);
            if (kp==(size_t)-1){ free_dict(dict); set_parse_error(error_message,pos); return NULL; }
            skip_ws(s,len,&kp);
            if (kp>=len || s[kp]!='='){ free(key); free_dict(dict); set_parse_error(error_message,kp); return NULL; }
            kp++;
            if (cur->key){ DictEntry*ne=malloc(sizeof(DictEntry)); cur->next=ne; cur=ne; }
            init_DictEntry(cur,key,klen); free(key);
            size_t vp=parse_value(s,len,kp,cur);
            if (vp==(size_t)-1){ free_dict(dict); set_parse_error(error_message,kp); return NULL; }
            pos=vp;
        }
        skip_ws(s,len,&pos);
    }

    char err[1024];
    if (DataLinkedList_to_data(dict,err)) {
        free_dict(dict);
        if (error_message) sprintf(error_message, "Failed to parse string (tree to dict)");
        return NULL;
    }
    return dict;
}
