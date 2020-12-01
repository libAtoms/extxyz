atoms_lines_tokenize_NB: atoms_lines_tokenize_NB.c
	gcc -g $< -o $@

parser_NB: parser_NB.c
	gcc -g $< -o $@

extxyz_kv_grammar.c extxyz_kv_grammar.h: extxyz_kv_NB_grammar.py
	python extxyz_kv_NB_grammar.py

parse_headers: extxyz_kv_grammar.c extxyz_kv_grammar.h parse_headers.c
	gcc -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c parse_headers.c -L${HOME}/libcleri/lib -lcleri -o $@
