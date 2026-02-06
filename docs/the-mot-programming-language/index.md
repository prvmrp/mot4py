The MOT programming language is used to describe a sequence of actions
that the experimental apparatus must perform.

#  Syntax {#syntax .unnumbered}

Program files are written in plain ASCII. Keywords are case sensitive
and are always uppercase. The syntax is described below from top to
bottom.

A parser for this syntax is implemented using the python package Lark.
The grammar file is\
`motpy4/src/mot4py/lang/motlang_0.1.0.lark`

The main configuration file for the program is\
`motpy4/src/mot4py/config/config.toml`

## Program structure {#program-structure .unnumbered}

-   A program is a sequence of loops. Often just a single loop is enough
    in most applications.

-   A loop begins with the keyword `LOOP` and ends with the keyword
    `ENDLOOP`. Every loop has four parts: comment, init, inner and
    iterator. The comment is optional, al least one between the init
    part and the combination of an inner part plus an iterator must be
    present.

-   A comment begins with `COMMENT` and ends with `ENDCOMMENT`. The
    comment is simply ignored during execution. It is used to describe
    (optionally) what the loop does or when was created and for which
    purpose. Lines starting with \# are ignored by the parser so can be
    used for comments but its use is not recommanding. When saving the
    file with a different name using the program they will be lost.

-   The init part is included between the keywords `INIT` and `ENDINIT`.
    Init contains a list of "things to do", from now on called
    *actions*, and defined more precisely later, before starting the
    execution i.e. setting the initial state. All the actions are
    executed in the order in which they appear. In the present version
    of the software the execution interval between consecutive actions
    in init is set to $\Delta T_i=30\,\mu\mathrm{s}$. The reason is
    that, with the firmware version used now in the DDS boards, changing
    frequency requires a bit less of $\Delta T_i$. It can be changed by
    adjusting `_initDT` in `functions.py`.

-   The inner part is included between the keywords `INNER` and
    `ENDINNER`. It contains a list of timed actions i.e. a series of
    lines containing a time and an action.

-   Every inner part must be associated with an iterator. The syntax for
    an iterator is simply `ITERATIONS N` where `N` is an integer number
    greater than zero. The iterator specifies how many times the inner
    part is executed before moving to the next loop. The maximum value
    for $N$ is limited by the FPGA memory. Depending on the FPGA model,
    the memory can accomodate programs up to either 8M or 32M actions.
    Loop are unrolled in the FPGA[^1] so a loop of 3 actions with
    $N=100$ counts as 300 actions. If a program is too long `mot4py`
    will complain and exit after loading the offending program.

To summarize: in every loop there is an init part executed only once to
set the initial condition and then a timed series of actions repeated
`N` times. A whole loop can be temporarily disabled by adding the
keyword `IDLE` on the same line, after the `LOOP` keyword. Example of
the loop structure:

    LOOP
    COMMENT
    This is just a comment
    ENDCOMMENT

    #These are line comments
    #They can be anywhere in the file
    #If possible avoid them

    INIT
    Set some initial conditions

    ENDINIT

    INNER
    Do something useful
    ENDINNER

    ITERATIONS 5
    ENDLOOP

## Time syntax {#time-syntax .unnumbered}

Times can be relative or absolute. A relative time is an absolute time
with a `+` sign before. Absolute times refer to the beginning of the
current iteration while relative times refer to the previous action.

Absolute times are decimal numbers (not in exponential notation i.e.
1.23 is valid 1.24e-3 is not) followed by units. Valid units are:
`s, ms, us, ns`, case insensitive.

Times are internally stored in ns so the minimum time different from
zero in the internal representation is 1ns. The maximum time, on the
other hand is essentially unlimited: up to 6840 s nothing happens. For
longer intervals dummy actions are automatically inserted every 6840 s
i.e. a relative time of 10 hours i.e. 36000 s can be specified but it
counts as 6 actions.

The minimum time interval that the hardware can accept is usually larger
than 1 ns. The present board with this software is limited to 100 ns so
the program reports an error when two actions are too close.

On the other hand a relative time of 0 ns can be acceptable in one
specific case i.e. when two actions can be combined into one. As an
example consider setting different bits on the same digital output
board. This case is recognised and accepted (at least with the currently
supported hardware).

## Actions syntax {#actions-syntax .unnumbered}

Actions are divided in different classes. The present version of this
software recognizes 5 classes.

-   Simple: the action does not require any paramenter. Presently there
    are no boards requiring or supporting simple actions but they might
    be useful in future. Example: a board that sends a trigger pulse
    whenever anything is written to its address,

        Trigger

-   Binary: the action takes a binary argument: \"0/1\" or \"on/off\"
    (case insensitive) are both accepted. Example: driving a digital
    line,

        B Field Mosfet Switch = on 

-   Enumeration: the action takes a non negative integer subrange,
    expressed as an integer number in a $[0\dots n]$ range. The

    Example: the amplitude of a DDS channel.

        AOM Amplitude = [100]

-   Scalar: the action takes a real number as argument (with mandatory
    units). Example: writing a voltage to an Analog output channel,

        Control Voltage = 5.23 V

    A big warning here: at this stage the parser is really dumb and
    needs, after the = sign, a floating number with units so \"5. V\" is
    ok, \"5 V\" and \"5.1\" are not. Units are required, to force users
    keeping good habits, but immediately discarded so SI prefixes do not
    work: \"10. mV\" will be understood as \"10. V\". If, for your peace
    of mind, for example, you would like to specify frequencies in kHz
    and/or MHz instead of Hz, this is possible but requires a suitable
    *compile function* (more on this later).

-   Test: the action is used for generic a write instruction on the SPB
    bus. Takes an address in the $[0 \dots 127]$ range and an integer in
    the $[0 \dots 65535]$. Both the address and the data can be either
    in base 10 or base 16. This is typically used to test new harware
    without going through the trouble of configuring an output channel.
    Example

        Test [10] = 0x1000

Every action has a unique integer ID. IDs are small integer numbers and
are assigned in `config.toml`. Check the *Connections* table in the
*Help* menu to see which ID is associated to each action.

For example suppose that the action `B Field Mosfet Switch` has ID=7,
then it should be written in the file as

    B Field Mosfet Switch = On (7)

by appending the ID between parenthesis at the end. The reason for this
is that the parses uses only the ID to identify the action actually
ignoring the descriptive text i.e. you can write the line above as

    yada yada yada = On (7)

and the parser will be ok with it, You can write pretty much anything as
descriptive text as long as the ID is correct. Using *Save As..* within
the program restores the default text.

## Action modifiers {#action-modifiers .unnumbered}

There are three modifiers, case insensitive, than can be appended at the
end of an action, they are

-   `BREAK`: execution stops after this action. Can be restarted by
    sending an hardware trigger to the FPGA board;

-   `SKIP`: the action is not executed, shifting times;

-   `IDLE`: the action is not executed, preserving times.

On the difference between `SKIP` and `IDLE`: suppose we have three
actions separated by 1 ms. If the second instruction is \"skipped\" the
third is executed 1 ms after the first, if it is \"idled\" the third is
executed 2 ms after the first. Example:

    B Field Mosfet Switch = On (7) IDLE

## Ramps {#ramps .unnumbered}

Enumerations and scalar actions can be *ramped* to a final value
starting from the present one using the following syntax for
enumerations:

    RAMP  Some text TO [n] IN T (m STEPS) (k)

for a final state $n$ in a time $T$ in $m$ steps if the instruction has
ID=k. Example:

    RAMP AOM Amplitude TO [200] IN 20ms (10 STEPS) (10)

This is equivalent to 10 instructions equally spaced by 2 ms.

For a scalar action units must also be included. Example:

    RAMP Control Voltage TO 10.0 V IN 1ms (50 STEPS) (11) 

There is a second kind of ramp: `RAMPLOG` in order to be able to reach
the final value with a geometric progression.

## Indirect Units {#indirect-units .unnumbered}

Often it is better, for scalar actions, to use units that are directly
connected with experimental parameters. For example a RF frequency used
to drive the AOM generating the offset of the cooling frequency is maybe
better expressed in $\Gamma$ rather than in MHz.

It is possible to specify the name of a *conversion function* in
`config.toml` that converts a number in $\Gamma$ units to units
understood by the program, in this case Hz. Then of course you have to
write that function and place it in the file `functions.py`.

## A complete example {#a-complete-example .unnumbered}

Here is an example trying to illustrate as many features, or bugs, as
possible. Since `Mot B Current` is expressed in Ampere, it is implied
that a suitable compile function that converts Ampere to Volts has been
specified and implemented.

    LOOP

    COMMENT
    Test comment with some words and special characters /12/1_25@#
    second line
    ENDCOMMENT

    # a single line comment

    INIT
    MOT B Field = Off                                                     (14)
    Trigger = Off                                                          (0)  IDLE
    Mot B Current = 5.0 A                                                 (22) 
    Ref Cooler Amp = [1000]                                               (41) 
    Test Function [0x30] = 0                                            (1000)
    Test Function [0x20] = 1000                                         (1000)
    ENDINIT

    INNER
    1ms            MOT B Field = On                                       (14)
    +0ns           Trigger = On                                            (0)

    # another comment: better not to use them

    +1ms           MOT B Field = Off                                      (14)
    +1ms           Ref Cooler Lock Freq = 100000000.0 Hz                  (30)
    +1ms           Test Function [0x20] = 0                             (1000) SKIP
    +10us          RAMP Mot B Current TO [200] IN 1s (10 STEPS)           (41) 
    +91ms          Ref Cooler Amp = [10]                                  (31) 
    +1s            Test Function [0x30] = 0x78                          (1000) 
    +10us          RAMPLOG Mot B Current TO 3.0 A IN 1s (10 STEPS)        (22)
    +10ms          RAMPLOG Ref Cooler Amp TO [100] IN 1s (10 STEPS)       (31) 
    ENDINNER

    ITERATIONS 3

    ENDLOOP

    LOOP

    COMMENT
    Second loop
    ENDCOMMENT

    INIT
    MOT B Field = Off                                                     (14) 
    Mot B Current = 1.0 A                                                 (22) 
    ENDINIT

    ENDLOOP

[^1]: Any volunteer to implement a smarter Verilog code for the FPGA?
