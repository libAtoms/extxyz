CFLAGS="-I/usr/local/include"
LDFLAGS="-L/usr/local/lib"

grammar.c:
	python example.py

grammar: grammar.c
	gcc -o grammar grammar.c -lcleri
