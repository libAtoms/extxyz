CFLAGS="-I/usr/local/include"
LDFLAGS="-L/usr/local/lib"
CC=gcc

grammar: grammar.o main.o
	gcc $^ -o $@ -lcleri

grammar.c:
	python example.py



