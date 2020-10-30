`extxyz_kv_NB.py` is an attempt at construcing a pyleri grammar for the extxyz 1nd ("comment") line, i.e. a sequence of key=value pairs.  It just dumps the parse tree of a single line from stdin.  Here is an example input line that parses.

```bash
echo "sam=\"abc special []\" bob=[1, 2, 3] joe=3 barestr=two\\ words" | python extxyz_kv_NB.py
```