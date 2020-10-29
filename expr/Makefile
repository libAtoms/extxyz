all: expr expr.py

expr: expr.c.par
	unicc expr.c.par
	gcc -o expr expr.c.c

expr.py: expr.py.par
	unicc expr.py.par
