`extxyz_kv_NB_dumptree.py` and `extxyz_kv_NB_grammar.py` are an attempt at construcing a pyleri grammar for the extxyz 2nd ("comment") line, i.e. a sequence of key=value pairs.  It just dumps the parse tree of a single line from stdin.  Here is an example input line that parses.

```bash
echo "sam=\"abc special []\" bob=[1, 2, 3] joe = 3 barestr=two\\ words" | python extxyz_kv_NB_dumptree.py
```

and a test of various types of arrays
```bash
echo "a1 = [1, 2, 3] a2 = \"1.1 2.2 3.3\" " | python extxyz_kv_NB_dumptree.py
```
