CFLAGS="-I/usr/local/include"
LDFLAGS="-L/usr/local/lib"
CC=gcc

json: grammar.o main.o
	gcc $^ -o $@ -lcleri

grammar.c:
	python json.py



