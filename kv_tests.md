# key-value pair test

## ones that should work

* integer: all combinations of
    * initial sign in 
        * ''
        * '+'
        * '-'
    * followed by one of
        *  1
        *  12
        *  012
* float: all combinations of
    * initial sign in 
        * ''
        * '+'
        * '-'
    * main number in
        * 1.0
        * 1.
        * 1
        * 12.0
        * 12
        * 012.0
        * 012
        * 0.12
        * 00.12
        * 0.012
        * .012
    * followed by exponent in
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
                * 12
* boolean:
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
* string
    * bare string
        * string of all printable non-whitespace chars except =",\]\[\}\{\\
        * TRuE
        * 1.3k7
    * quoted string, all start and end with "
        * all bare strings from above
        * string of all printable non-whitespace chars, backslash escaping " and \\
        * "line one\\nline two"
        * "abc\\"def"
        * "abc\\\\def"
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
        * \[ array of string \]
        * \[ array of string, array of string \]
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
