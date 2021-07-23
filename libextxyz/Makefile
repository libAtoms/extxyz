LIBCLERI_PATH=../libcleri/Release

CFLAGS += $(shell ../pcre2-10.37/build/bin/pcre2-config --cflags) -I$(subst Release,inc,${LIBCLERI_PATH})
LDFLAGS += $(shell ../pcre2-10.37/build/bin/pcre2-config --libs8) 

QUIP_LDFLAGS = -L${QUIP_ROOT}/build/${QUIP_ARCH} -latoms -llapack -lblas -lgomp
QUIP_F90FLAGS = -I${QUIP_ROOT}/build/${QUIP_ARCH}

CC ?= gcc
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
	${F90} ${F90FLAGS} ${QUIP_F90FLAGS} -g -c $< -o $@

test_fortran_main.o: fextxyz.o extxyz.o extxyz_kv_grammar.o

fextxyz: test_fortran_main.o fextxyz.o extxyz.o extxyz_kv_grammar.o
	${F90} -g $^ -o $@ ${LIBCLERI_PATH}/libcleri.a  ${LDFLAGS} ${QUIP_LDFLAGS}

cextxyz: test_C_main.o extxyz.o extxyz_kv_grammar.o
	${F90} -g $^ -o $@ ${LIBCLERI_PATH}/libcleri.a  ${LDFLAGS}

clean:
	rm -rf libextxyz.${dlext} *.o

