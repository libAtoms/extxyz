# key-value pair test

## ones that should work

* scalar integer: all combinations of
    * initial sign in 
        * ''
        * '+'
        * '-'
    * followed by one of
        *  1
        *  12
        *  012
    * "3"
    * " 3"
    * "3 "
    * " 3 "
    * {3}
    * { 3}
    * {3 }
    * { 3 }
* scalar float: all combinations of
    * initial sign in 
        * ''
        * '+'
        * '-'
    * main number in
        * 1.0
        * 1\.
        * 1
        * 12.0
        * 012.0
        * 12
        * 012
        * 0.12
        * 00.12
        * 0.012
        * .012
    * for main number -12.0, all exponent combinations of
        * ''
        * one of 
            * 'e', 
            * 'E'
            * 'd'
            * 'E'
            * followed by sign, one of
                * ''
                * '+'
                * '-'
            * followed by one of
                * 0
                * 2
                * 02
                * 12
* scalar boolean:
    * 't'
    * 'T'
    * 'true'
    * 'True'
    * 'TRUE'
    * 'f'
    * 'F'
    * 'false'
    * 'False'
    * 'FALSE'
* scalar string
    * bare string
        * string of all ASCII printable (32-127) non-whitespace chars except =",\]\[\}\{\\
        * TRuE
        * 1.3k7
        * \-2.75e
        * \+2.75e\-
    * quoted string, all start and end with "
        * all bare strings from above
        * string of all printable non-whitespace chars, backslash escaping " and \\
        * "line one\\nline two"
* 1-d array
    * backward compatible
        * int
            * "1 2 3"
        * float and promotion
            * "1.0 2.0 3.0"
            * "1 2.0 3"
            * "1.0 2 3"
        * bool
            * "T F True FALSE"
        * all prev with \{ \} instead of "
    * new style
        * all backward compat but surrounded by \[ \] and separated by commas
        * string
            * [ "a", "b" ]
            * [ a, b ]
            * [a,b]
            * ["a","b"]
            * [ a, "b", "c" ]
            * [ a, "b", c ]
            * [ "a", b, c ]
            * [ "a", b, "c" ]
            * [ "a, b", "c]" ]
            * [ T, F, bob ]
            * [ T, F, "bob" ]
            * [ T, F, bob, TRUE ]
            * [ T, F, "bob", TRUE ]
* 2-d array
    * integer
        * \[ array of int \]
        * \[ array of int, array of int \]
    * float
        * \[ array of float \]
        * \[ array of float, array of float \]
        * \[ array of int, array of float \]
    * bool
        * \[ array of bool \]
        * \[ array of bool, array of bool \]
    * string
        * \[ array of string, mix of bare and quoted \]
        * \[ array of string, array of string \]
        * \[ array of bare strings, array of quoted string \]
        * \[ array of quoted strings, array of bare string \]
        * \[ array of bool-like, array of string \]
        * \[ array of int-like, array of string \]
        * \[ array of bool-like, array of int-like, array of string, array of string \]
* bare string tests with (or w/o, whichever wasn't done before) space around =

## ones that should fail

* no key-value =
    * bare key, not = or value
* almost bare string
    * abc + &lt;char> + def, &lt;char> is one of
        * " = , \\ \[ \] \{ \} &lt;some whitespace>
* almost quoted string
    * 'abc'
    * "abc'
    * "abc\"def
* bad 1d array
    * "1, 2 }
    * {1, 2 "
    * [ 1, 2, ]
    * [ , 2, 3 ]
* bad 2d array
    * \[ \[ 1, 2 \], \[ 3 \] \]
    * \[ \[ 1, 2 \] \[ 1, 2 \] \]
