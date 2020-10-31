`extxyz_kv_NB_dumptree.py` and `extxyz_kv_NB_grammar.py` are an attempt at construcing a pyleri grammar for the extxyz 2nd ("comment") line, i.e. a sequence of key=value pairs.  It just dumps the parse tree of a single line from stdin.  Here is an example input line that parses.

```bash
echo "sam=\"abc special []\" bob=[1, 2, 3] joe = 3 barestr=two\\ words" | python extxyz_kv_NB_dumptree.py
```

and a test of various types of arrays
```bash
echo 'a1 = [1, 2, 3] a2 = "1.1 2.2 3.3" ' | python extxyz_kv_NB_dumptree.py
```

There is a routine that actually constructs a corresponding (info-like) dict in `extxyz_kv_NB_to_dict.py`.  Here is an example with all types (but not all variants) of everything except 2-D arrays
```bash
echo "aa = [1, 2, 3] aaq = \"1.1 2.2 3.3\" aac={a b c} ai=5 af=4.6e-3 ab=T as=bob aqs=\"this is a test\"" | python extxyz_kv_NB_to_dict.py
```

and here are some some 2-D arrays
```bash
echo 'i=45 f=6.5 b=T ai = [1, 3, 5] af={4  5  6.1} ai2 = [[1,2,3],[4,5,6]] af2 = [[1,2,3], [4,5,6.1]]' | python extxyz_kv_NB_to_dict.py
```

`atoms_lines_tokenize_NB.c` is a much simpler, hopefully faster, tokenizer for per-atom lines.  It returns one whitespace-separated token at a time.  Any non-EOL (ASCII 10, 13) characters within matching "s or preceded by \ are allowed.  Types are known from `Properties` key, so tokens are ready to be fed into `sscanf` with known formats. Quotes that are unmatched by EOL or a escaping backslash as the final character trigger errors.

here are some things that parse OK until error=2 (final backslash)
```bash
echo ' 1   5454 1e4   a  other\ test "this is a \" test" joe  befoe"test"aft\"er \' | ./atoms_lines_tokenize_NB
```
