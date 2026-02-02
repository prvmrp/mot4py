"""Parsing and ast generation for mot programming language."""

import time
from importlib.resources import files
from pathlib import Path

from lark import Lark, ParseTree, visitors

from mot4py.functions import *
from mot4py.utils import *


class Parser():
    """Class implementing code parsing and AST generation."""

    def __init__(self, fname: str, fundict: dict):
        """
        Parse the program.

        Args:
            fname: the program path or a multiline string
            fundict: a dictionary with all the functions and function codes
        """
        self._grammar = files("mot4py.lang").joinpath(
            "motlang_0.1.0.lark").read_text()
        self.parser = Lark(self._grammar, parser="lalr")
        self.fname = fname
        self.fundict = fundict
        self.loops = []
        if self.fname.find('\n') < 0:
            self._parse(self.parser.parse(open(self.fname).read()))
        else:
            self._parse(self.parser.parse(self.fname))
        self.compiled = []
        self._compile()
        self.len = self._calc_len()

    def _parse(self, tree):
        """Recursively parse the tree and create function objects."""
        for l in tree.children:
            self.loops.append(Interpreter(self.fundict).visit(l))

    def _compile(self):
        """Recursively call the compile method of the function objects."""
        for l in self.loops:
            if l.en:
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

        Creates a file with name `program_name.loop.{i}.vcd` for each loop in the file.
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
        cmt = ''
        init = []
        inner = []
        it = None

        for c in tree.children:
            if c.data == 'cmd':
                en = not self.visit(c)[0]  # only SKIP makes sense here
            elif c.data == 'comment':
                for d in self.visit(c):
                    if isinstance(d, list):
                        cmt += d[0] + '\n'
                if cmt:
                    cmt = cmt[:-1]
            elif c.data == 'init':
                init.extend(self.visit_children(c))
            elif c.data == 'inner':
                inner.extend(self.visit_children(c))
            elif c.data == 'iterator':
                it = int(self.visit(c)[0])
        return Loop(cmt, init, inner, it, en)

    def time(self, tree: ParseTree) -> tuple[bool, int]:
        """
        Create a time tuple from the AST.

        Args:
            tree: The AST input.

        Returns:
            : Time tuple. The first element is true if the time is
                relative, the second is the time in ns.
        """
        rel = False
        for c in tree.children:
            if c.data == 'reltime':
                rel = True
            elif c.data == 'abstime':
                t = float(c.children[0].value)
            elif c.data == 'timeunits':
                if not c.children:
                    mult = 1_000_000_000
                else:
                    d = c.children[0]
                    if d == 'm':
                        mult = 1_000_000
                    elif d == 'u':
                        mult = 1_000
                    elif d == 'n':
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
            MOT4PyError: If the action code is not declared in the function
                dictionary.
        """
        idle = False
        br = False
        nop = False
        rd = {}
        addr = None
        un = None
        for c in tree.children:
            if c.data == 'simple':
                val = None
            elif c.data == 'binary':
                for d in c.children:
                    if d.data == 'on':
                        val = True
                        break
                    if d.data == 'off':
                        val = False
                        break
            elif c.data == 'enum':
                for d in c.children:
                    if d.data == 'enumval':
                        val = int(d.children[0])
                        break
            elif c.data == 'scalar':
                for d in c.children:
                    if d.data == 'scalarval':
                        val = float(d.children[0])
                        un = str(d.children[1].children[0])
                        break
            elif c.data == 'test':
                addr, val = self.visit(c)
            elif c.data == 'ramp':
                val = None
                rd = self.visit(c)
            elif c.data == 'code':
                code = int(c.children[0])
                fun = None
                # TODO fundict should work in the opposite way, to have fast
                # lookup (codes should be values)
                for v in self.fundict.values():
                    if code == v.ID:
                        fun = v
                        break
                if fun is None:
                    raise MOT4PyError('Code (%d) not declared' % (code))
            elif c.data == 'cmd':
                idle, br, nop = self.visit(c)
        return Action(fun, val, un, not idle, br, nop, rd, addr)

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
                s = c.children[0]
                val = int(s, 16) if s.startswith('0x') else int(s)
            elif c.data == 'testaddr':
                s = c.children[0]
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
                rd['end'] = float(c.children[0])
                rd['units'] = str(c.children[1].children[0])
            elif c.data == 'enumval':
                rd['end'] = int(c.children[0])
            elif c.data == 'time':
                rel, t = self.visit(c)
                if rel:
                    raise MOT4PyError('Relative time in RAMP')
                else:
                    rd['time'] = t
            elif c.data == 'nsteps':
                rd['steps'] = int(c.children[0])
        return rd

    def cmd(self, tree: ParseTree) -> tuple[bool, bool]:
        """
        Return a command tuple from the AST.

        Args:
            tree: The input AST.

        Returns:
            en, br, nop: A tuple indicating if an SKIP, BREAK or IDLE command has been
                given
        """
        en = False
        br = False
        nop = False
        for c in tree.children:
            if c.upper() == 'SKIP':
                en = True
            if c.upper() == 'BREAK':
                br = True
            if c.upper() == 'IDLE':
                nop = True
        return (en, br, nop)
