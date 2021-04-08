PCRE2_CFLAGS=$(shell pcre2-config --cflags )
PCRE2_LIBS=$(shell pcre2-config --libs8 )

default: libcleri extxyz_kv_grammar.c extxyz_kv_grammar.h _extxyz.so

libcleri:
	if [ -z ${LIBCLERI_PATH} ]; then echo "LIBCLERI_PATH must be defined" 1>&2; exit 1; fi
	cat ${LIBCLERI_PATH}/makefile > ${LIBCLERI_PATH}/makefile.extxyz
	echo "" >> ${LIBCLERI_PATH}/makefile.extxyz
	cat libcleri_makefile_addition >> ${LIBCLERI_PATH}/makefile.extxyz
	${MAKE} -C ${LIBCLERI_PATH} CFLAGS=${PCRE2_CFLAGS} -f makefile.extxyz libcleri.a

extxyz_kv_grammar.c extxyz_kv_grammar.h: extxyz_kv_grammar.py
	python3 extxyz_kv_grammar.py
	# fix pyleri bug that makes double quote token string """ instead of "\""
	# sed -i -e 's/"""/"\\""/' extxyz_kv_grammar.c

atoms_lines_tokenize_NB: atoms_lines_tokenize_NB.c
	gcc -g $< -o $@

parser_NB: parser_NB.c
	gcc -g $< -o $@


parse_headers: extxyz_kv_grammar.c extxyz_kv_grammar.h parse_headers.c
	gcc -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c parse_headers.c  ${LIBCLERI_PATH}/libcleri.a ${PCRE2_LIBS} -o $@

parse_C: parse_C.c extxyz.c extxyz_kv_grammar.c extxyz_kv_grammar.h
	gcc -g -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c extxyz.c parse_C.c ${LIBCLERI_PATH}/libcleri.a ${PCRE2_LIBS} -o $@

_extxyz.so: libcleri extxyz.c extxyz_kv_grammar.c extxyz_kv_grammar.h
	gcc -fPIC -shared -g -I/opt/local/include -I${HOME}/libcleri/include extxyz_kv_grammar.c extxyz.c ${LIBCLERI_PATH}/libcleri.a ${PCRE2_LIBS} -o $@

clean:
	rm -rf extxyz_kv_grammar.c extxyz_kv_grammar.h atoms_lines_tokenize_NB parser_NB parse_headers _extxyz.so _extxyz.so.DSYM
