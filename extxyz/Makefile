LIBCLERI_PATH=${PWD}/libcleri/Release

default: extxyz_kv_grammar.c extxyz_kv_grammar.h _extxyz.so

libcleri:
	make -C ${LIBCLERI_PATH} libcleri.a

extxyz_kv_grammar.c extxyz_kv_grammar.h: extxyz_kv_grammar.py
	python3 extxyz_kv_grammar.py
	# fix pyleri bug that makes double quote token string """ instead of "\""
	# sed -i -e 's/"""/"\\""/' extxyz_kv_grammar.c

atoms_lines_tokenize_NB: atoms_lines_tokenize_NB.c
	gcc -g $< -o $@

parser_NB: parser_NB.c
	gcc -g $< -o $@

parse_headers: extxyz_kv_grammar.c extxyz_kv_grammar.h parse_headers.c
	gcc -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c parse_headers.c  ${LIBCLERI_PATH}/libcleri.a -lpcre2-8 -o $@

parse_C: parse_C.c extxyz.c extxyz_kv_grammar.c extxyz_kv_grammar.h
	gcc -g -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c extxyz.c parse_C.c ${LIBCLERI_PATH}/libcleri.a -lpcre2-8 -o $@

_extxyz.so: libcleri extxyz.c extxyz_kv_grammar.c extxyz_kv_grammar.h
	gcc -shared -g -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c extxyz.c ${LIBCLERI_PATH}/libcleri.a -lpcre2-8 -o $@

clean:
	rm -f extxyz_kv_grammar.c extxyz_kv_grammar.h atoms_lines_tokenize_NB parser_NB parse_headers
