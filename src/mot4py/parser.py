"""Parsing and ast generation for mot programming language."""

import time
from importlib.resources import files
from pathlib import Path

from lark import Lark, ParseTree, visitors

from mot4py.functions import Action, Loop, Simple, Test, TimedAction


class Parser():
    """Class implementing code parsing and AST generation."""

    def __init__(self, fname: str, fundict: dict):
        """
        Parse the program.

        Args:
            fname: the program path
            fundict: a dictionary with all the functions and function codes
        """

        # TODO: in future, each file should specify a specific vesion of the
        # parser
        self._grammar = files("mot4py.lang").joinpath(
            "motlang_0.1.0.lark").read_text()
        self.parser = Lark(self._grammar, parser="lalr")
        self.fname = fname
        self.fundict = fundict
        self.tree = self.parser.parse(open(fname).read())
        self.loops = []
        self._parse()
        self.compiled = []
        self._compile()
        self.len = self._calc_len()

    def _parse(self):
        """Recursively parse the tree and create function objects."""
        for l in self.tree.children:
            self.loops.append(Interpreter(self.fundict).visit(l))

    def _compile(self):
        """Recursively call the compile method of the function objects."""
        for l in self.loops:
            self.compiled.append(l.compile())

    def _calc_len(self) -> int:
        """Calculate the length of the compiled actions."""
        sum = 0
        for l in self.compiled:
            i = -1
            for e in l:
                if e.get('first'):
                    i = l.index(e)
            if i < 0:
                sum += len(l)
            else:
                sum += i + (len(l) - i - 1) * l[-1].get('iter')
        return sum

    def __str__(self):
        ans = ''
        for l in self.loops:
            ans += str(l)
        return ans

    def wrVCD(self):
        """
        Create a .vcd file for each loop to view with gtkviewer.

        Creates a file with name `programname_{i}.vcd` for each loop in the file.
        """
        for i, l in enumerate(self.loops):
            if not l.en:
                continue

            acts = []
            ids = []
            tests = []
            # TODO refactor
            with open("%s.loop%d.vcd" % (Path(self.fname).stem, i + 1), 'w') as f:
                f.write('$timescale 1ns $end\n')
                f.write('$scope module loop $end\n')
                f.write('$date %s $end\n' % (time.asctime()))
                for a in l.init:
                    if a.en:
                        if isinstance(a.fun, Test):
                            if a.addr in tests:
                                continue
                            else:
                                tests.append(a.addr)
                                acts.append(a)
                        else:
                            if a.fun.ID in ids:
                                continue
                            else:
                                ids.append(a.fun.ID)
                                acts.append(a)
                for a in l.inner:
                    if a.action.en:
                        if isinstance(a.action.fun, Test):
                            if a.action.addr in tests:
                                continue
                            else:
                                tests.append(a.action.addr)
                                acts.append(a.action)
                        else:
                            if a.action.fun.ID in ids:
                                continue
                            else:
                                ids.append(a.action.fun.ID)
                                acts.append(a.action)
                for a in acts:
                    if isinstance(a.fun, Test):
                        f.write(a.fun.regVCD(a.addr))
                    else:
                        f.write(a.fun.regVCD())
                f.write('$upscope $end\n')
                f.write('$enddefinitions $end\n')
                f.write('$dumpvars\n')
                for a in acts:
                    f.write(a.fun.dvarVCD(a.val, a.addr))
                f.write('$end\n')
                l = self.compiled[i]
                k = 0
                start = 0
                stop = 0
                for a in l:
                    if a.get('first'):
                        start = k
                    if a.get('iter'):
                        stop = k
                        break
                    k += 1

                for a in l[start:stop]:
                    if a.get('en') and not a.get('nop'):
                        f.write("#%d\n" % (a['abst']))
                        if isinstance(a['fun'], Simple):
                            f.write(a['fun'].dvarVCD(1, a['addr']))
                            f.write("#%d\n" % (a['abst'] + Loop._minDT))
                            f.write(a['fun'].dvarVCD(0, a['addr']))
                        else:
                            f.write(a['fun'].dvarVCD(a['val'], a['addr']))


class Interpreter(visitors.Interpreter):
    """
    Interpreter class.

    Recursively visits a tree and builds the intermediate code (function
    object instances) corresponding to the parsed language construct.
    """

    def __init__(self, fundict: dict):
        """
        Initialize interpreter instance.

        Args:
            fundict: a dictionary of actions and the associated codes.
        """
        super().__init__()
        self.fundict = fundict

    def loop(self, tree: ParseTree) -> Loop:
        """
        Create a Loop object by recursively visiting the AST.

        Args:
            tree: The parsed syntax tree input.

        Returns:
            : Structure containing the intermediate code for the program.

        Todo:
            Check whether this function raises any exceptions.
        """
        en = True
        cmt = None
        init = []
        inner = []
        it = None

        for c in tree.children:
            if c.data == 'en':
                en = False  # TODO Why is en false if 'en' is encountered?
            elif c.data == 'comment':
                cmt = self.visit_children(c)[0]
            elif c.data == 'init':
                init.extend(self.visit_children(c))
            elif c.data == 'inner':
                inner.extend(self.visit_children(c))
            elif c.data == 'iterator':
                it = self.visit(c)

        return Loop(cmt, init, inner, it, en)

    def _concat(self, tree: ParseTree) -> str:
        """Concatenate text into a python string, remove the last letter."""
        ans = ''
        for c in tree.children:
            ans += c.value
            if c.value != '\n':
                ans += ' '
        return ans[:-1]

    def ctext(self, tree: ParseTree) -> str:
        """
        Create string from comment text.

        Args:
            tree: The AST input.

        Returns:
            : concatenated string.
        """
        return self._concat(tree)

    def text(self, tree: ParseTree) -> str:
        """
        Create string from text.

        Args:
            tree: The AST input.

        Returns:
            : concatenated string.
        """
        return self._concat(tree)

    def time(self, tree: ParseTree) -> tuple[bool, int]:
        """
        Create a time tuple from the AST.

        Args:
            tree: The AST input.

        Returns:
            : Time tuple. The first element is true if the time is
                relative, the second is the time amount in ns.
        """
        rel = False
        for c in tree.children:
            if c.data == 'reltime':
                rel = True
                # TODO Check: reltime and abstime should only have one children,
                # so iteration would not be needed
                for d in c.children:
                    if d.data == 'abstime':
                        for e in d.children:
                            t = float(e)
            elif c.data == 'abstime':
                for d in c.children:
                    t = float(d)
            elif c.data == 'timeunits':
                mult = 1_000_000_000
                for d in c.children:
                    if d.data == 'milli':
                        mult = 1_000_000
                    elif d.data == 'micro':
                        mult = 1_000
                    elif d.data == 'nano':
                        mult = 1
        return (rel, int(t * mult))

    def action(self, tree: ParseTree) -> Action:
        """
        Create action object from AST.

        Args:
            tree: Input AST.

        Returns:
            : Action object.

        Raises:
            ValueError: If the action code is not declared in the function
                dictionary.
        """
        idle = False
        br = False
        rd = {}
        addr = None
        for c in tree.children:
            if c.data in ('simple', 'binary', 'enum', 'scalar'):
                val = self.visit(c)
            elif c.data == 'test':
                addr, val = self.visit(c)
            elif c.data == 'ramp':
                val = None
                rd = self.visit(c)
            elif c.data == 'code':
                code = self.visit(c)
                fun = None
                # TODO fundict should work in the opposite way, to have fast
                # lookup (codes should be values)
                for v in self.fundict.values():
                    if code == v.ID:
                        fun = v
                        break
                if fun is None:
                    raise ValueError('Code (%d) not declared' % (code))
            elif c.data == 'cmd':
                idle, br = self.visit(c)
        return Action(fun, val, not idle, br, rd, addr)

    def taction(self, tree: ParseTree) -> TimedAction:
        """
        Create TimedAction object from AST.

        Args:
            tree: The input AST.

        Returns:
            : TimedAction object with the parsed action and time.
        """
        for c in tree.children:
            if c.data == 'time':
                rel, t = self.visit(c)
            elif c.data == 'action':
                a = self.visit(c)
        return TimedAction(rel, t, a)

    def simple(self, _tree: ParseTree) -> None:
        """
        Create a simple action object from AST. Equivalent to a NOP.

        Args:
            _tree: The input AST. IGNORED

        Returns:
            : None
        """
        return None

    def binary(self, tree: ParseTree) -> bool:
        """
        Return the status value of the parsed binary action.

        Args:
            tree: The input AST.

        Returns:
            : if the binary action is on or off
        """
        for c in tree.children:
            if c.data == 'on':
                return True
            elif c.data == 'off':
                return False

    def enum(self, tree: ParseTree) -> int:
        """
        Convert an enum value to its integer representation.

        Args:
            tree: The input AST.

        Returns:
            : the conversion to integer of the enum value.
        """
        for c in tree.children:
            if c.data == 'enumval':
                for d in c.children:
                    return int(d)

    def scalar(self, tree: ParseTree) -> float:
        """
        Convert a scalar value to its float representation.

        Args:
            tree: The input AST.

        Returns:
            : the conversion to float of the enum value.
        """
        for c in tree.children:
            if c.data == 'scalarval':
                for d in c.children:
                    if isinstance(d, str):
                        return float(d)

    def test(self, tree: ParseTree) -> tuple[int, int]:
        """
        Convert test value and test address into integers.

        Args:
            tree: The input AST.

        Returns:
            addr, val: a tuple with the integer test address and integer test
                value
        """
        for c in tree.children:
            if c.data == 'testval':
                for d in c.children:
                    s = d.value
                    val = int(s, 16) if s.startswith('0x') else int(s)
            elif c.data == 'testaddr':
                for d in c.children:
                    s = d.value
                    addr = int(s, 16) if s.startswith('0x') else int(s)
        return addr, val

    def ramp(self, tree: ParseTree) -> dict:
        """
        Create a ramp dictionary from the AST.

        Args:
            tree: The input AST.

        Returns:
            : a dictionary representing the ramp
        """
        rd = {}
        for c in tree.children:
            if c.data == 'ramplin':
                rd['log'] = False
            elif c.data == 'ramplog':
                rd['log'] = True
            elif c.data == 'scalarval':
                for d in c.children:
                    if isinstance(d, str):
                        rd['end'] = float(d)
            elif c.data == 'enumval':
                for d in c.children:
                    if isinstance(d, str):
                        rd['end'] = int(d)
            elif c.data == 'time':
                rel, t = self.visit(c)
                if rel:
                    raise ValueError('Relative time in RAMP')
                else:
                    rd['time'] = t
            elif c.data == 'nsteps':
                for d in c.children:
                    if isinstance(d, str):
                        rd['steps'] = int(d)
        return rd

    def code(self, tree: ParseTree) -> int:
        """
        Return the code number from the AST.

        Args:
            tree: The input AST.

        Returns:
            : the integer action code.
        """
        for c in tree.children:
            if isinstance(c, str):
                return int(c)

    def cmd(self, tree: ParseTree) -> tuple[bool, bool]:
        """
        Return a command tuple from the AST.

        Args:
            tree: The input AST.

        Returns:
            en, br: A tuple indicating if an IDLE or a BREAK command has been
                given
        """
        en = False
        br = False
        for c in tree.children:
            if c.data == 'en':
                en = True
            if c.data == 'br':
                br = True
        return (en, br)

    def iterator(self, tree: ParseTree) -> int:
        """
        Return the number of iterations from the iterator construct.

        Args:
            tree: The input AST.

        Returns:
            : the number of iterations to be executed.
        """
        for c in tree.children:
            if isinstance(c, str):
                return int(c)
