LIBCLERI_PATH=../libcleri/Release
PCRE2_CFLAGS=$(pcre2-config --cflags)

default: libcleri

all: libcleri extxyz_kv_grammar.c extxyz_kv_grammar.h

libcleri:
	if [ -z ${LIBCLERI_PATH} ]; then echo "LIBCLERI_PATH must be defined" 1>&2; exit 1; fi
	cat ${LIBCLERI_PATH}/makefile > ${LIBCLERI_PATH}/makefile.extxyz
	echo "" >> ${LIBCLERI_PATH}/makefile.extxyz
	echo "libcleri.a: $(OBJS) $(USER_OBJS)" >> ${LIBCLERI_PATH}/makefile.extxyz
	echo "\tar rcs libcleri.a $(OBJS) $(USER_OBJS)" >> ${LIBCLERI_PATH}/makefile.extxyz
	${MAKE} -C ${LIBCLERI_PATH} CFLAGS=${PCRE2_CFLAGS} -f makefile.extxyz libcleri.a

extxyz_kv_grammar.c extxyz_kv_grammar.h: ../python/extxyz_kv_grammar.py
	python3 ../python/extxyz_kv_grammar.py

clean:
	rm -rf _extxyz.so _extxyz.so.DSYM
