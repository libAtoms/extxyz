LIBCLERI_PATH=../libcleri/Release

CFLAGS += $(shell pcre2-config --cflags)
LDFLAGS += $(shell pcre2-config --libs8)

F90 ?= gfortran
prefix ?= /usr/local
libdir ?= $(prefix)/lib

UNAME := $(shell uname)
ifeq ($(UNAME), Darwin)
	dlext  ?= dylib
else ifeq ($(UNAME), Windows)
	dlext  ?= dll
else
	dlext  ?= so
endif

default: libextxyz.${dlext}

all: libcleri extxyz_kv_grammar.c extxyz_kv_grammar.h libextxyz.${dlext}

libcleri:
	if [ -z ${LIBCLERI_PATH} ]; then echo "LIBCLERI_PATH must be defined" 1>&2; exit 1; fi
	cat ${LIBCLERI_PATH}/makefile > ${LIBCLERI_PATH}/makefile.extxyz
	echo "" >> ${LIBCLERI_PATH}/makefile.extxyz
	echo "libcleri.a: $(OBJS) $(USER_OBJS)" >> ${LIBCLERI_PATH}/makefile.extxyz
	echo "\tar rcs libcleri.a $(OBJS) $(USER_OBJS)" >> ${LIBCLERI_PATH}/makefile.extxyz
	${MAKE} -C ${LIBCLERI_PATH} -f makefile.extxyz libcleri.a

extxyz_kv_grammar.c: ../grammar/extxyz_kv_grammar.py
	pip3 install pyleri
	python3 ../grammar/extxyz_kv_grammar.py

libextxyz.${dlext}: libcleri extxyz.c extxyz_kv_grammar.c
	${CC} ${CFLAGS} -shared -fPIC -o $@ -g extxyz.c extxyz_kv_grammar.c ${LIBCLERI_PATH}/libcleri.a ${LDFLAGS}

install: libextxyz.${dlext}
	mkdir -p ${libdir}
	cp libextxyz.${dlext} ${libdir}

%.o: %.c
	${CC} ${CFLAGS} -g -c $< -o $@

%.o: %.f90
	${F90} ${F90FLAGS} -g -c $< -o $@

fextxyz: main.o fextxyz.o extxyz.o extxyz_kv_grammar.o
	${F90} -g $^ -o $@ ${LIBCLERI_PATH}/libcleri.a  ${LDFLAGS}

clean:
	rm -rf libextxyz.${dlext} *.o
