import time
from pathlib import Path

from lark import Lark, visitors

from .Functions import *


class Parser():

    _grammar = r"""
    start: loop+
    loop: _NL* "LOOP" en? _NL+ comment? (init | (inner iterator) | (init inner iterator)) "ENDLOOP" _NL*
    
    comment: "COMMENT" _NL+ ctext "ENDCOMMENT" _NL*
    ctext: (WORD+ WS+)+
    text: (WORD | WS_INLINE)+
    init: "INIT" _NL action+ "ENDINIT" _NL*
    inner: "INNER" _NL+ taction+ "ENDINNER" _NL*
    taction: time action
    iterator: "ITERATIONS" INT _NL*
    
    time: (abstime | reltime) timeunits
    reltime: "+" abstime
    abstime: (DECIMAL|INT)
    timeunits: (milli|micro|nano)? "s"i
    milli: "m"
    micro: "u"
    nano: "n"
    
    action: ( simple | binary | enum | scalar | test | ramp) "(" code ")" cmd? _NL+
    cmd: en|br
    en: "IDLE"i
    br: "BREAK"i
    code: INT
    
    simple: text
    
    binary: text "=" (on | off)
    on: "1" | "on"i
    off: "0" | "off"i

    enum: text "=" enumval
    enumval:  "[" INT "]"

    scalar: text "=" scalarval
    scalarval: (SIGNED_NUMBER | NUMBER) units
    units: WORD

    test: text testaddr "=" testval
    HEXINT: "0x" HEXDIGIT+
    testaddr: "[" (INT | HEXINT) "]"
    testval: (INT | HEXINT)

    ramp: (ramplin|ramplog) text "TO" (scalarval|enumval) "IN" time "(" nsteps "STEPS)"
    ramplin: "RAMP"
    ramplog: "RAMPLOG"
    nsteps: INT

    %import common.NEWLINE -> _NL
    %import common.WORD
    %import common.INT
    %import common.HEXDIGIT
    %import common.DECIMAL
    %import common.NUMBER
    %import common.SIGNED_NUMBER
    %import common.WS_INLINE
    %import common.WS
    %import common._STRING_INNER

    %ignore WS_INLINE
    """

    def __init__(self, fname, fundict):
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
        for l in self.tree.children:
            self.loops.append(Interpreter(self.fundict).visit(l))

    def _compile(self):
        for l in self.loops:
            self.compiled.append(l.compile())

    def _calc_len(self):
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

    def format(self):
        ans = ''
        for l in self.loops:
            ans += l.format()
        return ans

    def wrVCD(self):
        i = 0
        for l in self.loops:
            if l.en:
                acts = []
                ids = []
                tests = []
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
                            f.write(a.fun._regVCD(a.addr))
                        else:
                            f.write(a.fun._regVCD())
                    f.write('$upscope $end\n')
                    f.write('$enddefinitions $end\n')
                    f.write('$dumpvars\n')
                    for a in acts:
                        f.write(a.fun._dvarVCD(a.val, a.addr))
                    f.write('$end\n')
                    skip = True
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
                            f.write(a['fun']._dvarVCD(a['val'], a['addr']))
            i += 1


class Interpreter(visitors.Interpreter):

    def __init__(self, fundict):
        super().__init__()
        self.fundict = fundict

    def loop(self, tree):
        en = True
        cmt = None
        init = []
        inner = []
        it = None
        for c in tree.children:
            if c.data == 'en':
                en = False
            elif c.data == 'comment':
                cmt = self.visit_children(c)[0]
            elif c.data == 'init':
                init.extend(self.visit_children(c))
            elif c.data == 'inner':
                inner.extend(self.visit_children(c))
            elif c.data == 'iterator':
                it = self.visit(c)
        return Loop(cmt, init, inner, it, en)

    def _concat(self, tree):
        ans = ''
        for c in tree.children:
            ans += c.value
            if c.value != '\n':
                ans += ' '
        return ans[:-1]

    def ctext(self, tree):
        return self._concat(tree)

    def text(self, tree):
        return self._concat(tree)

    def time(self, tree):
        rel = False
        for c in tree.children:
            if c.data == 'reltime':
                rel = True
                for d in c.children:
                    if d.data == 'abstime':
                        for e in d.children:
                            t = float(e)
            elif c.data == 'abstime':
                for d in c.children:
                    t = float(d)
            elif c.data == 'timeunits':
                mult = 1000000000
                for d in c.children:
                    if d.data == 'milli':
                        mult = 1000000
                    elif d.data == 'micro':
                        mult = 1000
                    elif d.data == 'nano':
                        mult = 1
        return (rel, int(t * mult))

    def action(self, tree):
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
                for v in self.fundict.values():
                    if code == v.ID:
                        fun = v
                        break
                if fun is None:
                    raise ValueError('Code (%d) not declared' % (code))
            elif c.data == 'cmd':
                idle, br = self.visit(c)
        return Action(fun, val, not idle, br, rd, addr)

    def taction(self, tree):
        for c in tree.children:
            if c.data == 'time':
                rel, t = self.visit(c)
            elif c.data == 'action':
                a = self.visit(c)
        return TimedAction(rel, t, a)

    def simple(self, tree):
        return None

    def binary(self, tree):
        for c in tree.children:
            if c.data == 'on':
                return True
            elif c.data == 'off':
                return False

    def enum(self, tree):
        for c in tree.children:
            if c.data == 'enumval':
                for d in c.children:
                    return int(d)

    def scalar(self, tree):
        for c in tree.children:
            if c.data == 'scalarval':
                for d in c.children:
                    if isinstance(d, str):
                        return float(d)

    def test(self, tree):
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

    def ramp(self, tree):
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

    def code(self, tree):
        for c in tree.children:
            if isinstance(c, str):
                return int(c)

    def cmd(self, tree):
        en = False
        br = False
        for c in tree.children:
            if c.data == 'en':
                en = True
            if c.data == 'br':
                br = True
        return (en, br)

    def iterator(self, tree):
        for c in tree.children:
            if isinstance(c, str):
                return int(c)
