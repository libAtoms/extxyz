# Remaining issues
1. check more systematically two-d array of mixed row _types_ gives.  Mostly it tries to detect and give an error, but there are
still some weirdnesses.  pyleri will promote anything to a string in a single one-d array or row of a 2-d array, and int to float.  Promoting int to float between rows is easy, and now being done, but other promotions (to string) are harder, because we don't keep the original string anyplace (and without it there's no guarantee things like floats will be converted back to a string in the exact form they started).  We should decide what level of consistency we want to enforce.
2. check strings with various mismatched quotes, esp ones that do not conform to either bare or quoted string
3. make treatement of 9 elem old-1d consistent: now extxyz.py always reshapes (not just Lattice) to 3x3, but extxyz.c does not.

# Extended XYZ specification and parsing tools

## XYZ spec

### General formatting

- Allowed characters: printable subset of ASCII, single byte
- Allowed whitespace: plain space and tab (no fancy unicode nonbreaking space, etc)
- Allowed end-of line (EOL) characters set by implementation + OS
  - pure python: file iterator
  - low level c: fgets
- Blank lines: allowed only as 2nd line of each frame (for plain xyz) and at end of file

### General definitions

* regex: PCRE/python regular expression
* **Whitespace:** regex \s, i.e. space and tab

### **Primitive Data Types**

#### String

Sequence of one or more allowed characters, optionally quoted, but **must** be quoted in some circumstances.
*   Allowed characters - all except newline
*   Entire string **may be** surrounded by double quotes, as first and last characters (must match). 
    Quotes inside string that are same as containing quotes must be escaped with backslash.
*   Strings that contain one of the following characters **must** be quoted 
    * whitespace (regex \\s)
    * backslash, represented by double backslash \\\\
    * newline, represented by \\n
    * single quote ' or double quote "
    * open or close square bracket \[ \] or curly brackets \{ \}
*   Backslash \: only present in quoted string, only used for escaping quotes, encode literal backslash with a 
    double backslaw(\\\\), and encoding newline (\\n)
*   Must conform to one of the following regex
    * quoted string: \("\)\(?:\(?=\(\\\\?\)\)\\2.\)\*?\\1
    * bare \(unquoted\) string: \(?:\[^\\s='",\}\{\\\]\\\[\\\\\]|\(?:\\\\\[\\s='",\}\{\\\]\\\]\\\\\]\)\)\+
*   only used in comment line key-value pairs, not per-atom data

#### Simple string

Sequence of one or more allowed characters, unquoted (i.e. even outermost quotes are part of string), and without whitespace 
*   allowed characters - regex \\S, i.e. all except newline and whitespace
*   regex \\S\+
*   only used in per-atom data, not comment line key-value pairs

#### Logical/boolean

*   [tT] or [fF] or [tT]rue or [fF]alse or TRUE or FALSE
*   regex
    * true: \(?:T|\[tT\]rue|TRUE\)
    * false: \(?:F|\[fF\]alse|FALSE\)

#### Integer number

string of one or more decimal digits, optionally preceded by sign
*   regex \[\+\-\]?\[0\-9\]\+

#### Floating point number

possibly non-integer finite precision real number
*   optional leading sign \[\+\-\], decimal number including optional decimal point \., 
    optional \[dDeE\] folllowed by exponent consisting of optional sign followed by string of 
    one or more digits
*   regex \[\+\-\]?(?:\[0\-9\]\+\[\.\]?\[0\-9\]\*|\\.\[0\-9\]\+)(?:\[dDeE\]\[\+\-\]?\[0\-9\]\+)?

### Order for identifying primitive data types, accept first one that matches
*   bool
*   int
*   float
*   bare string containing no whitespace or special characters
*   quoted string starting and ends with double quote and containing only allowed characters

#### one dimensional array (vector)

sequence of one or more of the same primitive type
*   new style: opens with \[, one or more of the same primitives separated by commas ',', ends with \]
*   backward compatible: opens with " or \{, one or more of the same primitive types except strings,
    separated by spaces, ends with matching " or \}
*   primitive data type is determined by same priority as single primitive item, but must be satisfied
    by entire list simultaneously.  E.g. all intgers will result in an integer array, but a mix
    of integer and float will result in a float array.

#### two dimensional array (matrix)

sequence of one or more new style one dimensional arrays of the same length and type
*   opens with \[, one or more new style one dimensional arrays separated by commas ',', ends with \]
*   all contained one dimensional arrays in a single two dimensional array must have same number and 
    primitive data type elements

### **XYZ file**

A concatenation of 1 or more FRAMES (below), with optional blank lines at the end (but not between frames)

#### **FRAME**

*   Line 1: a single integer &lt;N&> preceded and followed by optional whitespace
*   Line 2: zero or more per-config key=value pairs (see key-value pairs below)
*   Lines 3..N+2: per-atom data lines with M columns each (see Properties and Per-Atom Data below)

#### **key=value pairs**

Associates per-configuration value with key.  Spaces are allowed around = sign, which do not become part of the key or value. 

Key: bare or quoted string

Value: primitive type, 1-D array, or 2-D array.  Type is determined from context according to order specified above.

For backward compatibility, single entry backward compatible array is interpreted as a scalar

#### **Special key "Properties”**: defines the columns in the subsequent lines in the frame. 

*   If after full parsing the key “Properties” is missing, the format is retroactively assumed to be plain xyz (4 columns, Z/species x y z), the entire second line is stored as a per-config “comment” property, and columns beyond the 4th are not read. 
*   Value is a string with the format of a series of triplets, separated by “:”, each triplet having the format: “&lt;name>:&lt;T>:&lt;m>”. 
    *   The &lt;name> (string) names the column(s), &lt;T> is a one of “S”, “I”, “R”, “L”, and indicates the type in the column, “string”, “integer”, “real”, “logical”, respectively. &lt;m> is an integer specifying how many consecutive columns are being referred to.  The sum of &lt;m>s must be M.

#### **Per-atom data lines**

Each column can contain one of any primitive type, except string, which is replaced with simple string, separated by one or more whitespace characters, ending with EOL (optional for last line)

## READING ase.atoms.Atoms FROM THIS FORMAT

Specific keys indicate special values, with specific order for overriding

Key-value pairs:

*   Lattice -> Atoms.cell, optional [do we want to accept "cell" also?]
    *   3x3 matrix - rows are cell vectors [preferred]
    *   9-vector - 3 cell vectors concatenated [only for backward compat]
    *   3-vector - diagonal entries of cell matrix [?]
*   pbc -> Atoms.pbc, optional
    *   3-vector of bool
    *   default [False]*3 if no Lattice, otherwise [True]*3
*   Calculator results, used to set SinglePointCalculator.results dict
    *   all per-config properties in ase.calculator.all_properties, with same name
    *   scalars, vectors - directly stored
    *   stress
        *   6-vector Voigt
        *   9-vector, 3x3 matrix, stored as stress Voigt-6, fail if not symmetric
    *   virial -> stress (to convert multiply by -1/cell_vol), same format as stress [warn/fail if stress also present, perhaps only if inconsistent?]

Properties keys (all types are per-atom), types are simple

*   Atoms
    *   Z -> numbers
    *   species -> numbers, fail if not valid chemical symbol [warn/fail if conflict with Z?]
    *   pos -> positions
    *   mass -> masses
    *   velo -> momenta (get mass from atomic number if missing)
    *   same name: initial\_charges, initial\_magmoms
*   Calculator.results
    *   local\_energy \-> energies
    *   forces \-> forces [also support “force”? What about overriding, complain if inconsistent?]
    *   same name: magmoms (scalar or 3-vector), charges

### WRITING ase.atoms.Atoms TO THIS FORMAT

General considerations

*   platform-appropriate EOL
*   [require some specific whitespace convention?]
*   scalars
    *   all strings are quoted 
    *   otherwise stored unquoted
*   arrays
    *   use {} [or []?] container marks, comma separated (not backward compatible " and space separated forms)
*   Definitely store (naming as described below)
    *   all "first-class" Atoms properties (cell, pbc, numbers, masses, positions, momenta [any others?])
    *   all info keys that are scalar, 1-D, 2-D array of prim type
    *   all arrays that are scalar (Natoms x 1) or 1-D array( Natoms x (m > 1)) of prim type, shape[1] mapped to number of columns and space separated, not using regular array notation
    *   [optionally warn about un-representable quantities?]
*   all Calculator.results key-value pairs, per-config same as info, per-atom same as arrays
*   Perhaps store
    *   all info keys, per-config calculator results that are not representable (i.e. not prim type scalar, 1-D, or 2-D for per-config only) but can be mapped to JSON, as string starting with "\_JSON "
    *   same for arrays [?]
*   In general, keep ASE data type/dimension, invert mapping of names for reading. For quantities that have multiple possible names, use:
    *   Lattice, not cell, 3x3 matrix
    *   velo, not momenta
    *   stress, not virial, as 3x3 matrix [are we OK with this?]
