# Extended XYZ specification and parsing tools

## XYZ spec

### General considerations and questions:

1. Proposed (non-trivial) violations of backward compatibility:
    1. [spec below is currently written for backward compatibility, but this option would make things cleaner] No longer accept “ for 1-d arrays?  Alternative is to write possibly fiddly logic for deciding based on content whether a particular quoted thing is actually a 1-D array rather than a string, and therefore inability to have strings that consist of just numbers, for example.
    2. [spec below breaks backward compat this way] No more bare keyword as shortcut for keyword=T (currently this allows command line parsing to use same logic, and I’m not sure we can give up on that syntax for the CLI parsing)
2. Is it OK that the proposed level of quoting flexibility and backslash escaping probably means a real parser, rather than using simple regex or split on whitespace? Would limiting allowed characters (e.g. excluding comma, quotes, array containers from bare strings) make parsing simpler?
3. Is it an active good to move to our own repo, so we don’t have Ask second-guessing every change?
4. Is there a good way to use the grammar itself to define special key-value pairs, or is that something to be handled by the code that _uses_ the output of the auto-generated parser?

### General formatting

- Allowed end-of line (EOL) characters: unix + windows (cr vs crlf, etc)
- Allowed whitespace: plain space (not fancy unicode nonbreaking space, etc), tab
- Blank lines: only as 2nd line of each frame (for plain xyz) and at end of file

### General definitions

* **Whitespace:** space and tab
* **String:** sequence of allowed characters.  Must be quoted in some circumstances.
*   Allowed characters: all non-whitespace printable ASCII (or some more modern variant thereof, perhaps even more general unicode) + whitespace as defined above
*   Explicit newlines are not allowed, must be represented by \n
*   Entire string may be surrounded by single or double quotes, as first and last characters (must match). Quotes inside string that are same as containing quotes must be escaped with backslash.
*   String **must** be quoted if it contains whitespace.
*   Backslash: only used to escape quotes, encode literal backslash (\\), and encode newline (\n)
*   [is this enough, or do we need to backslash escape other special characters like comma or array containers {} []?]

### Other primitive data types

*   Logical/bool : single character T or F
*   Int: regex [0-9]+ (or simply as interpreted by language-specific parsing routines?)
*   Float: regex -?([0-9]+\(.[0-9]*)?|\.[0-9]+)([dDeE][+-]?[0-9]+)? (or simply as interpreted by language-specific parsing routines after simple conversions like [dD]->[eE]?)

**XYZ file**

is a concatenation of 1 or more FRAMES, with optional blank lines at the end (but not between frames)

**FRAME**

*   Line 1: a single integer &lt;N> preceded and followed by optional whitespace
*   Line 2: zero or more per-config key=value pairs
*   Lines 3..N+2: per-atom data lines with M columns each

**Logic for identifying primitive data types, accept first one that matches**

*   Looks like bool (above): bool
*   Looks like int (above): int
*   Looks like float (above): float
*   Starts with single or double quote: string, must end with matching quote, otherwise fail
*   Else (bare) string, can’t have whitespace (should we allow backslash escape of whitespace here?)

**key=value pairs**

Associates per-configuration value with key.  Spaces are allowed around = sign, which get eaten and are therefore not part of the key or value. 

Key: valid string (or a smaller subset of characters? What about other types as keys?)

Value:

*   Primitive type (string, bool, int, float) scalar
*   1-D or 2-D array of entries that are all the same primitive type

Value type is determined from context in the following order, until first match

*   Starting with quote and contains one or more of a single type from bool, int, float (not string), separated by regex (\s+|\s*,\s*) [ugly, needed for backward compat] 
    *   If one entry, scalar of corresponding type
    *   If more than one, 1-D array of corresponding type
    *   [might be useful to be able to designate that something is a quoted string even if it looks like a number, but I don’t know of a current use case for that]
*   Starting with array container character {} or []: 1-D or 2-D array of primitive type. 
    *   Array items separated by whitespace or comma regex (\s+|\s*,\s*), 2-D array rows separated by same regex [again allowing space is a bit ugly, just comma is cleaner, but needed for backward compat]
    *   If open/close char doesn’t match, or number of items in each row of an apparently 2-D array isn’t equal, fail.
    *   Elements are primitive data types, matching logic as above, except no bare strings here (too confusing to parse with commas, etc)
    *   No entirely sure how implement this - need data types of _all_ entries to decide if consistent array can be made (e.g. promote int to float if needed).  What about mix of things that look like numbers and things that don’t - demote all to strings, or error?
*   Otherwise, match primitive data type by logic above

**Special key** “**Properties”: **defines the columns in the subsequent lines in the frame. 

*   If after full parsing the key “Properties” is missing, the format is retroactively assumed to be plain xyz (4 columns, Z/species x y z), the entire second line is stored as a per-config “comment” property, and columns beyond the 4th are not read. 
*   Value is a string with the format of a series of triplets, separated by “:”, each triplet having the format: “&lt;name>:&lt;T>:&lt;m>”. 
    *   The &lt;name> (string) names the column(s), &lt;T> is a one of “S”, “I”, “R”, “L”, and indicates the type in the column, “string”, “integer”, “real”, “logical”, respectively. &lt;m> is an integer specifying how many consecutive columns are being referred to.  The sum of &lt;m>s must be M.

**Per-atom data lines**

Each column can contain one of any primitive type, same syntax as above (including bare strings), separated by one or more whitespace characters, ending with EOL (optional for last line)

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
    *   same name: initial_charges, initial_magmoms
*   Calculator.results
    *   local_energy -> energies
    *   forces -> forces [also support “force”? What about overriding, complain if inconsistent?]
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
    *   all info keys, per-config calculator results that are not representable (i.e. not prim type scalar, 1-D, or 2-D for per-config only) but can be mapped to JSON, as string starting with "_JSON " 
    *   same for arrays [?]
*   In general, keep ASE data type/dimension, invert mapping of names for reading. For quantities that have multiple possible names, use:
    *   Lattice, not cell, 3x3 matrix
    *   velo, not momenta
    *   stress, not virial, as 3x3 matrix [are we OK with this?]
