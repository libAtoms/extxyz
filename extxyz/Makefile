extxyz_kv_grammar.c extxyz_kv_grammar.h: extxyz_kv_grammar.py
	python3 extxyz_kv_grammar.py
	# fix pyleri bug that makes double quote token string """ instead of "\""
	# sed -i -e 's/"""/"\\""/' extxyz_kv_grammar.c

atoms_lines_tokenize_NB: atoms_lines_tokenize_NB.c
	gcc -g $< -o $@

parser_NB: parser_NB.c
	gcc -g $< -o $@

parse_headers: extxyz_kv_grammar.c extxyz_kv_grammar.h parse_headers.c
	gcc -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c parse_headers.c -L${HOME}/libcleri/lib -lcleri -o $@

parse_C: parse_C.c extxyz.c extxyz_kv_grammar.c extxyz_kv_grammar.h
	gcc -g -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c extxyz.c parse_C.c -L${HOME}/libcleri/lib -lcleri -lpcre -o $@

extxyz.so: extxyz.c extxyz_kv_grammar.c extxyz_kv_grammar.h
	gcc -shared -g -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c extxyz.c -L${HOME}/libcleri/lib -lcleri -lpcre -o $@

clean:
	rm -f extxyz_kv_grammar.c extxyz_kv_grammar.h atoms_lines_tokenize_NB parser_NB parse_headers
