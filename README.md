# Chip
Chip is a language that processes streams of bytes in a manner not
dissimilar to an integrated circuit. A Chip circuit is a
3-dimensional specification; most computation occurring in
2-dimensions, with pins to allow layers to interact. Each element
interacts with its von Neumann neighborhood (that is, no diagonals)
according to specific rules, described below.

Input is processed byte by byte, and each byte is split into its
component bits. All computation in Chip occurs at the bit level,
using elements such as an 'and' gate, a half-adder, and a memory
cell. Output is provided by packing the relevant bits back into a
byte, and outputting that value.

## Language specification
A Chip circuit is made up of the elements described here:

| Lexeme                | * | Description
| -------------------- | --- | ---
| <code>HGFEDCBA</code> |   | 8 bits of the input data; A is LSbit; value given on all sides; may be used multiple times; when input is exhausted, program terminates (end identifier like NUL is recommended for programs that need to continue after input is done)
| <code>hgfedbca</code> |   | 8 bits of output data; a is LSbit; value is taken from all sides; may be used multiple times (as usual, all sides/uses are or'd before output)
|                       |   |
| <code>76543210</code> |   | 8 bits wide stack memory; inactive without 89 controls (produces lows); when both read and write are high behaves like Zz; unable to read or write to another stack bit directly
| <code>8</code>        |   | Stack read memory control; when given high stack is in read state; not altered by Ss controls; reading an empty stack produces lows; if not set, stack can still be read, but won't be popped this cycle
| <code>9</code>        |   | Stack write memory control; when given high stack is in write state; not altered by Ss controls
|                       |   |
| <code>┼+</code>       |   | wire; connect on all sides; first form is (U+253C)
| <code>─-</code>       |   | wire; horizontal connect only; first form is (U+2500)
| <code>│&#124;</code>  |   | wire; vertical connect only; first form is (U+2502); other elements marked with * also connect north/south like this wire
| <code>×x</code>       |   | wire; crossing, north connects to south, and west to east; first form is (U+00D7)
| <code>┬v</code>       |   | wire; tee connecting all but north; first form is (U+252C)
| <code>├></code>       |   | wire; tee connecting all but west; first form is (U+251C)
| <code>┤\<</code>      |   | wire; tee connecting all but east; first form is (U+2524)
| <code>┴^</code>       |   | wire; tee connecting all but south; first form is (U+2534)
| <code>┘'</code>       |   | wire; connect north and west; first form is (U+2518)
| <code>└`</code>       |   | wire; connect north and east; first form is (U+2514)
| <code>┐.</code>       |   | wire; connect south and west; first form is (U+2510)
| <code>┌,</code>       |   | wire; connect south and east; first form is (U+250C)
|                       |   |
| <code>Mm</code>       | * | 1-bit memory cell; write from west when high on north/south, read from east; lowercase is horizontally mirrored
| <code>Zz</code>       |   | 1-cycle buffer; input on west or north, output value from previous cycle on east or south; outputs low on first cycle; lowercase is horizontally mirrored
| <code>?</code>        |   | Random; each cycle produces high or low randomly; each instance is a unique and independent source
| <code>!</code>        |   | Pulse; produces a 1-tick pulse on the first cycle; useful for init tasks
|                       |   |
| <code>$</code>        |   | Sleep; induces a sleep before next cycle, depending on number of sides powered. From zero to four, in seconds: 0, 1/10, 1/4, 1/2, 1. Multiple sleep/pause elements are summed.
| <code>Pp</code>       |   | Pause; induces a sleep before next cycle, depending on the current stack head. P sleeps for stack_head seconds, p for stack_head/256 seconds. Multiple sleep/pause elements are summed.
|                       |   |
| <code>»</code>        |   | diode; west is in, east is out, north and south ignored; form is (U+00BB)
| <code>«</code>        |   | diode; horizontally mirrored of above; form is (U+00AB)
| <code>⌐~</code>       |   | not diode; west is in, east is out, north and south ignored; first form is (U+2310)
| <code>¬÷</code>       |   | not diode; horizontally mirrored of above; first form is (U+00AC); second form is (U+00F7)
| <code>]</code>        | * | and; west, north/south are in, east is out
| <code>[</code>        | * | and; horizontally mirrored of above
| <code>)</code>        | * | or; west, north/south are in, east is out
| <code>(</code>        | * | or; horizontally mirrored of above
| <code>}</code>        | * | xor; west, north/south are in, east is out
| <code>{</code>        | * | xor; horizontally mirrored of above
|                       |   |
| <code>/</code>        | * | switch; when north/south is high, west is connected to east as a wire, disconnected otherwise
| <code>\\</code>       | * | switch; when north/south is low, west connected to east as a wire, disconnected otherwise
|                       |   |
| <code>#@</code>       |   | half-adder; west and north inputs, east is result, south is carry; <code>@</code> is horizontally mirrored
|                       |   |
| <code>*</code>        |   | high constant; transmits in all directions (low constant is unneeded)
|                       |   |
| <code>Oo</code>       |   | pin; connects up and down to aligned pin of same case on neighboring layers; acts as + wire on current layer, except to neighboring pin of same case
| <code>=</code>        |   | layer divider; must occur at beginning of line, remainder of line is ignored; implied at start and end of file
|                       |   |
| <code>:</code>        |   | block comment start marker; everything read until comment end marker is a comment; stays in comment state past newlines; the newlines are kept, all other characters become empty space
| <code>;</code>        |   | block comment end marker; error unless paired with comment start marker; comment nesting is not supported
|                       |   |
| <code>Kk</code>       |   | when polled on a side, this element will poll the other side(s), then cache that value until the next cycle; each of the four sides are cached separately; primarily for optimization and performance; K behaves like +, and k behaves like x.
|                       |   |
| <code>T</code>        |   | terminates exection if powered on any side; output DOES NOT occur for the cycle when termination occurs
| <code>t</code>        |   | same as above, but output DOES occur for the current cycle; shorthand for ZT
| <code>S</code>        |   | skips output for this cycle; allows multiple inputs per output
| <code>s</code>        |   | keep current input for next cycle; allows multiple outputs per input
| <code>X</code>        |   | examines values for debugging, reads signals on all sides (or'ing if necessary), and prints the value to verbose output

* Elements marked with an asterisk let signals pass north-south unaffected, e.g. allowing easy control of multiple gate or memory cells.

# Examples
These examples are largely limited to 4 bits or less for simplicity.
More examples may be found in the specs/ directory, which use all 8
bits.

###### Layers and pins (a is A, b and c stay low)
```text
A--o    o-o-a
=
b-ooO   o O-c
=
    O---o
```

###### Memory/buffer, change value if all were high last time
```text
 CBA
D]]]Z.
|||`-Ma
||`--Mb
|`---Mc
`----Md
```

###### Invert and reverse
```text
A~d
B~c
C~b
D~a
```

###### Full adder
```text
 AB
C##a
 `)c
```

###### Increment
```text
 *
A#a
B#b
C#c
D#d
 e
```

###### Add current and previous numbers
```text
AZ
##a BZ
`)--##b CZ
    `)--##c DZ
        `)--##d
            `)e
```

###### Running sum (no overflow)
```text
,-va
ZA|,-vb
##'ZB|,-vc
`)-##'ZC|,-vd
   `)-##'ZD|
      `)-##'
```

###### Running sum (no overflow) (unicode)
```text
┌─┬a
ZA│┌─┬b
##┘ZB│┌─┬c
└)─##┘ZC│┌─┬d
   └)─##┘ZD│
      └)─##┘
```

###### Add current and previous (layers)
```text
AZA
 ##a
o('
=
 BZB
,-##b
oo('
=
  CZC
 ,-##c
 oo('
=
   DZD
  ,-##d
  o `)e
```

###### High on first tick, low after
```text
*Z~a
```

###### High, then low, then high, then low...
```text
,-.
Z~^a
```

###### Halt 2 ticks after A is low
```text
 A
*\ZZT
```

###### Filter out inputs with high A and high B
```text
 B
A]S
ab
```

###### T-flipflop; switches out when in is high
```text
,¬. 
ZM^a
 A
```
