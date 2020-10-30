`extxyz_kv_NB_dumptree.py` and `extxyz_kv_NB_grammar.py` are an attempt at construcing a pyleri grammar for the extxyz 2nd ("comment") line, i.e. a sequence of key=value pairs.  It just dumps the parse tree of a single line from stdin.  Here is an example input line that parses.

```bash
echo "sam=\"abc special []\" bob=[1, 2, 3] joe = 3 barestr=two\\ words" | python extxyz_kv_NB_dumptree.py
```

and a test of various types of arrays
```bash
echo 'a1 = [1, 2, 3] a2 = "1.1 2.2 3.3" ' | python extxyz_kv_NB_dumptree.py
```

actual dict construction of all types (but not all variants) of everything except 2-D arrays
```bash
echo "aa = [1, 2, 3] aaq = \"1.1 2.2 3.3\" aac={a b c} ai=5 af=4.6e-3 ab=T as=bob aqs=\"this is a test\"" | python extxyz_kv_NB_to_dict.py
```

and some 2-D arrays
```bash
echo 'i=45 f=6.5 b=T ai = [1, 3, 5] af={4  5  6.1} ai2 = [[1,2,3],[4,5,6]] af2 = [[1,2,3], [4,5,6.1]]' | python extxyz_kv_NB_to_dict.py
```
