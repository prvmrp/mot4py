"""Classes representing intermediate code objects."""
from . import spbboards


def cAO1_2(val):
    """MISTERY. Halve the argument.

    Todo:
        See if used in the codebase, else delete.
    """
    return 0.5 * val


class Function():
    """Generic class for a function type.

    Todo:
        - Make this an Abstract Base Class, then make all other functions inherit
        this.
        - What is the difference between a function and an action?
    """

    _funtype = ('Simple', 'Binary', 'Enum', 'Scalar', 'Test')

    def __init__(self, n, id, d, brds):
        """TODO"""
        self.name = n
        self.ID = id
        self.desc = d.get('desc')
        self.fmt = d.get('fmt')
        self.units = d.get('units')
        self.comp = d.get('compile')
        self.max = d.get('max')
        self.min = d.get('min')
        brd, self.ch = n.split('_')
        self.brd = brds.get(brd)

    def val2hex(self, val, board=None):
        """TODO"""
        return val

    @classmethod
    def genfun(self, name, id, d, brds):
        """TODO"""
        t = d.get('type')
        if t not in self._funtype:
            raise ValueError('Unknown function type: ' + name)
            return
        else:
            for b in self._funtype:
                if t == b:
                    return eval(b + '(name, id, d, brds)')

    def format(self):
        """TODO"""
        return self.desc


class Simple(Function):
    """TODO"""

    def __init__(self, n, id, d, brds):
        """TODO"""
        super().__init__(n, id, d, brds)
        if self.comp is None:
            raise ValueError(
                "The Simple function %s requires a compile field" % (self.desc))
            return

    def val2hex(self, val):
        """TODO"""
        return eval(self.comp + '()')

    def format(self, val, addr):
        """TODO"""
        return str.ljust(super().format(), 60)

    def _regVCD(self):
        """TODO"""
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var wire 1 %d %s $end\n" % (self.ID, name)

    def _dvarVCD(self, val, addr):
        """TODO"""
        return "1%d\n" % (self.ID)


class Binary(Function):
    """TODO"""

    def val2hex(self, val):
        """TODO"""
        self.brd.set_val(val, self.ch)
        return self.brd.param2val(val, self.ch)

    def format(self, val, addr):
        """TODO"""
        ans = super().format()
        ans += " = " + ("On" if val else "Off")
        return str.ljust(ans, 60)

    def _regVCD(self):
        """TODO"""
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var reg 1 %d %s $end\n" % (self.ID, name)

    def _dvarVCD(self, val, addr):
        """TODO"""
        return "%d%d\n" % (1 if val else 0, self.ID)


class Enum(Function):
    """TODO"""

    def val2hex(self, val):
        """TODO"""
        if self.brd._lutmax >= val:
            self.brd.set_val(val, self.ch)
            return val
        else:
            raise ValueError('Invalid state %d for function %s' %
                             (val, self.desc))

    def format(self, val, addr):
        """TODO"""
        ans = super().format() + (" = [%d]" % (val))
        return str.ljust(ans, 60)

    def _regVCD(self):
        """TODO"""
        name = self.desc.replace(' ', '_').replace('.', '_')
        if self.max:
            j = self.max.bit_length()
        else:
            j = 16
        return "$var reg %d %d %s [%d:0] $end\n" % (j, self.ID, name, j-1)

    def _dvarVCD(self, val, addr):
        """TODO"""
        return "%s %d\n" % (bin(val)[1:], self.ID)


class Scalar(Function):
    """TODO"""

    def __init__(self, n, id, d, brds):
        """TODO"""
        super().__init__(n, id, d, brds)
        if not self.fmt:
            self.fmt = "%.3f%"
        if not self.units:
            self.units = "A.U.%"

    def val2hex(self, val):
        """TODO"""
        if self.comp:
            v1 = eval(self.comp + ('(%f)' % (val)))
        else:
            v1 = val
        self.brd.set_val(val, self.ch)
        return self.brd.param2val(v1, self.ch)

    def format(self, val, addr):
        """TODO"""
        ans = super().format()
        fmt = self.fmt if self.fmt else "%.1f"
        un = " " + self.units if self.units else ""
        ans += (" = " + fmt + un) % (val)
        return str.ljust(ans, 60)

    def _regVCD(self):
        """TODO"""
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var real 64 %d %s $end\n" % (self.ID, name)

    def _dvarVCD(self, val, addr):
        """TODO"""
        return "r%.16g %d\n" % (val, self.ID)


class Test(Function):
    """TODO"""

    def val2hex(self, val):
        """TODO"""
        return val

    def format(self, val, addr):
        """TODO"""
        ans = super().format()
        ans += " [%s] = %s" % (addr, val)
        return str.ljust(ans, 60)

    def _regVCD(self, addr):
        """TODO"""
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var reg 16 A%d ADDR_%d [15:0] $end\n" % (addr, addr)

    def _dvarVCD(self, val, addr):
        """TODO"""
        return "%s A%d\n" % (bin(val)[1:], addr)


class Action():
    """TODO"""

    def __init__(self, fun, val, en=False, br=False, ramp={}, addr=None):
        """TODO"""
        self.fun = fun
        self.val = val
        self.en = en
        self.br = br
        self.ramp = ramp
        self.addr = addr if addr is not None else self.fun.brd.get_addr(
            self.fun.ch)

    def format(self, sz):
        """TODO"""
        if self.ramp:
            if not isinstance(self.fun, (Enum, Scalar)):
                raise ValueError("Invalid ramp for fun %s" % self.fun.desc)
            if self.ramp['log']:
                ans = "RAMPLOG "
            else:
                ans = "RAMP "
            ans += self.fun.format(self.ramp['end'],
                                   None).rstrip().replace('=', 'TO', 1)
            ans += " IN %s " % (TimedAction.timefmt(None,
                                False, self.ramp['time']))
            ans += "(%d STEPS) " % self.ramp['steps']
            if len(ans) < sz:
                ans = str.ljust(ans, sz)
        else:
            ans = str.ljust(self.fun.format(self.val, self.addr), sz)
        ans += str.ljust("(%d)" % (self.fun.ID), 5)
        if not self.en:
            ans += " IDLE"
        if self.br:
            ans += " BREAK"
        ans += '\n'

        return ans

    def _unramp(self, atime):
        """TODO"""
        delta = self.ramp['end'] - self.val
        if self.val != 0:
            ratio = self.ramp['end'] / self.val
        else:
            raise ValueError("log ramp starting from 0\n")
        dt = self.ramp['time'] // self.ramp['steps']
        if self.ramp['log']:
            dv = ratio ** (1. / self.ramp['steps'])
        else:
            dv = delta / self.ramp['steps']
        l = []
        v0 = self.val
        for i in range(self.ramp['steps'] + 1):
            if self.ramp['log']:
                self.val = v0 * (dv ** i)
            else:
                self.val = v0 + dv * i
            l.append({'abst': atime, 'val': self.val})
            atime += dt
        return l

    def compile(self, cval, atime=0):
        """TODO"""
        db = isinstance(self.fun.brd, spbboards.DO16)
        aux = {'addr': self.addr, 'en': self.en,
               'br': self.br, 'db': db, 'fun': self.fun}
        if not self.ramp:
            hexval = self.fun.val2hex(self.val)
            return [{'abst': atime, 'val': self.val, 'bin': hexval} | aux,]
        else:
            self.val = cval['ids'][self.fun.ID]  # no ramps for Test Actions
            l = self._unramp(atime)
            for e in l:
                hexval = self.fun.val2hex(e['val'])
                e |= {'bin': hexval} | aux
            cval['ids'][self.fun.ID] = l[-1]['val']
            return l


class TimedAction():
    """TODO"""

    def __init__(self, rel, time, act):
        """TODO"""
        self.rel = rel
        self.time = time
        self.action = act

    def format(self, sz):
        """TODO"""
        ts = self.timefmt(self.rel, self.time)
        return str.ljust(ts, 15) + self.action.format(sz - 15)

    def timefmt(self, rel, time):
        """TODO"""
        ans = '+' if rel else ''
        prefix = 'ns'
        if time % 1000 == 0:
            time /= 1000
            prefix = 'us'
        if time % 1000 == 0:
            time /= 1000
            prefix = 'ms'
        if time % 1000 == 0:
            time /= 1000
            prefix = 's'
        ans += ("%d" % (time)) + prefix
        return ans

    def compile(self, cval, atime):
        """TODO"""
        if self.rel:
            atime += self.time
        else:
            atime = self.time
        return self.action.compile(cval, atime)


class Loop():
    """Intermediate code representation of loop code."""
    # minimum time delta (clock period) in ns
    _minDT = 100
    # maximum time delta in ns
    _maxDT = 6_840_000_000_000

    def __init__(self, cmt, init, inner, it, en):
        """
        Initialize the representation of the loop.

        args:
            cmt: loop comment
            init: initialization actions
            inner: inner actions
            it: iterator
            en: enabled flag

        todo:
            - define types of arguments in implementation
        """
        self.cmt = cmt
        self.init = init
        self.inner = inner
        self.it = it
        self.en = en

    def format(self) -> str:
        """Return a formatted string representation of the loop."""
        # TODO maybe this method should be a __str__?
        ans = ''
        en = '' if self.en else ' IDLE'
        ans += 'LOOP' + en + '\n'
        if self.cmt:
            ans += '\nCOMMENT\n' + self.cmt + '\nENDCOMMENT\n'
        if self.init:
            ans += '\nINIT\n'
            for a in self.init:
                ans += a.format(75)
            ans += 'ENDINIT\n'
        if self.inner:
            ans += '\nINNER\n'
            for a in self.inner:
                ans += a.format(75)
            ans += 'ENDINNER\n'
        if self.it:
            ans += '\nITERATIONS ' + str(self.it) + '\n'
        ans += '\nENDLOOP\n\n'
        return ans

    def compile(self) -> list:
        """
        Compile the looplist and all its subactions, and manage the action times.

        returns:
            : a list of actions in the loop

        todo:
            - Check timing logic
        """
        # early exit if disabled
        if not self.en:
            return []

        looplist = []  # representation of loop as a list
        cval = {'ids': {}, 'addrs': {}}

        # actions absolute times start on the firt clock cycle
        atime = self._minDT
        # compile all enabled actions in the init section, append the results in
        # the looplist
        for a in self.init:
            if not a.en:
                continue
            l = a.compile(cval, atime)
            if isinstance(a.fun, Test):
                # test functions do not have an id
                cval['addrs'][a.addr] = a.val
            else:
                cval['ids'][a.fun.ID] = a.val
            # update the clock time
            # all initialization actions happen on subsequent clock cycles
            atime += self._minDT
            looplist.extend(l)

        ln = []  # intermediate action list
        # compile all enabled actions in the inner section, append the results
        # in the intermediate list
        for a in self.inner:
            # TODO check this loop for bugs. What happens when there is a
            # commented action with absolute or relative time?
            if a.action.en:
                l = a.compile(cval, atime)
                if isinstance(a.action.fun, Test):
                    cval['addrs'][a.action.addr] = a.action.val
                else:
                    cval['ids'][a.action.fun.ID] = a.action.val
                atime = l[0]['abst']
                ln.extend(l)
            else:
                # TODO Why absolute time here added to abolute time?
                # Shouldn't absolute time not be relative to previous time?
                atime += l[0]['abst']

        if ln:
            # sort all actions by their absolute time
            # TODO what happens to actions that do not have an absolute time?
            ln.sort(key=lambda v: v['abst'])
            # append iterator to list if more than one iteration
            if self.it > 1:
                ln[0]['first'] = True
                ln.append({'iter': self.it})
        # add intermediate list to looplist
        looplist.extend(ln)

        # populate the relative times from the absolute times
        # relative time initialization of the first action
        looplist[0]['relt'] = looplist[0].get('abst') // 100
        i = 1
        n = len(looplist)
        # do not include last iterator in the relative time loop
        if looplist[-1].get('iter'):
            n -= 1

        while i < n:
            if not looplist[i].get('iter'):
                # for the first action of a loop, just use its absolute time
                # TODO what happens if first action of a loop has relative time?
                if looplist[i].get('first'):
                    dt = looplist[i].get('abst')
                else:
                    dt = looplist[i].get('abst') - \
                        looplist[i - 1].get('abst')

                # TODO why the different behaviour between 0 and < minDT? Maybe
                # we can change < minDT to match 0 and raise warning instead of
                # error
                if 0 < dt < self._minDT:
                    raise ValueError('DT too small: %d ns ' % (dt))
                # TODO in which cases dt == 0 arises?
                elif dt == 0:
                    # TODO what is action db?
                    # in some conditions are met, get action away from looplist,
                    # else raise collision error
                    if (looplist[i]['addr'] == looplist[i - 1]['addr']) and looplist[i]['db'] and looplist[i - 1]['db']:
                        looplist[i]['first'] = looplist[i - 1].get('first')
                        looplist[i]['relt'] = looplist[i - 1].get('relt')
                        looplist.pop(i - 1)
                        i -= 1
                        n -= 1
                    else:
                        # TODO change ValueError to CollisionError, maybe
                        # CollisionWarning?
                        raise ValueError('Two actions at the same time: %d ns ' % (
                            looplist[i].get('abst')))
                # Insert nops if time delta is too big
                elif dt > self._maxDT:
                    mt = self._maxDT // 100
                    p = dt // self._maxDT
                    d = [{'nop': True, 'relt': mt}] * p
                    looplist[i]['relt'] = (dt % self._maxDT) // 100
                    looplist = looplist[:i] + d + looplist[i:]
                    i += p - 1
                    n += p - 1
                else:
                    looplist[i]['relt'] = dt // 100

                i += 1
            # if the action is an iterator (?), then skip this and set the time
            # of the next action to its absolute time
            else:
                looplist[i + 1]['relt'] = looplist[i +
                                                   1].get('abst') // 100
                i += 2

        return looplist
