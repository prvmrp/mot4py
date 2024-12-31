from mot4py import SPBBoards


def cAO1_2(val):
    return 0.5 * val


class Function():

    _funtype = ('Simple', 'Binary', 'Enum', 'Scalar', 'Test')

    def __init__(self, n, id, d, brds):
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
        return val

    @classmethod
    def genfun(self, name, id, d, brds):
        t = d.get('type')
        if t not in self._funtype:
            raise ValueError('Unknown function type: ' + name)
            return
        else:
            for b in self._funtype:
                if t == b:
                    return eval(b + '(name, id, d, brds)')

    def format(self):
        return self.desc


class Simple(Function):

    def __init__(self, n, id, d, brds):
        super().__init__(n, id, d, brds)
        if self.comp is None:
            raise ValueError(
                "The Simple function %s requires a compile field" % (self.desc))
            return

    def val2hex(self, val):
        return eval(self.comp + '()')

    def format(self, val, addr):
        return str.ljust(super().format(), 60)

    def _regVCD(self):
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var wire 1 %d %s $end\n" % (self.ID, name)

    def _dvarVCD(self, val, addr):
        return "1%d\n" % (self.ID)


class Binary(Function):

    def val2hex(self, val):
        self.brd.set_val(val, self.ch)
        return self.brd.param2val(val, self.ch)

    def format(self, val, addr):
        ans = super().format()
        ans += " = " + ("On" if val else "Off")
        return str.ljust(ans, 60)

    def _regVCD(self):
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var reg 1 %d %s $end\n" % (self.ID, name)

    def _dvarVCD(self, val, addr):
        return "%d%d\n" % (1 if val else 0, self.ID)


class Enum(Function):

    def val2hex(self, val):
        if self.brd._lutmax >= val:
            self.brd.set_val(val, self.ch)
            return val
        else:
            raise ValueError('Invalid state %d for function %s' %
                             (val, self.desc))

    def format(self, val, addr):
        ans = super().format() + (" = [%d]" % (val))
        return str.ljust(ans, 60)

    def _regVCD(self):
        name = self.desc.replace(' ', '_').replace('.', '_')
        if self.max:
            j = self.max.bit_length()
        else:
            j = 16
        return "$var reg %d %d %s [%d:0] $end\n" % (j, self.ID, name, j-1)

    def _dvarVCD(self, val, addr):
        return "%s %d\n" % (bin(val)[1:], self.ID)


class Scalar(Function):

    def __init__(self, n, id, d, brds):
        super().__init__(n, id, d, brds)
        if not self.fmt:
            self.fmt = "%.3f%"
        if not self.units:
            self.units = "A.U.%"

    def val2hex(self, val):
        if self.comp:
            v1 = eval(self.comp + ('(%f)' % (val)))
        else:
            v1 = val
        self.brd.set_val(val, self.ch)
        return self.brd.param2val(v1, self.ch)

    def format(self, val, addr):
        ans = super().format()
        fmt = self.fmt if self.fmt else "%.1f"
        un = " " + self.units if self.units else ""
        ans += (" = " + fmt + un) % (val)
        return str.ljust(ans, 60)

    def _regVCD(self):
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var real 64 %d %s $end\n" % (self.ID, name)

    def _dvarVCD(self, val, addr):
        return "r%.16g %d\n" % (val, self.ID)


class Test(Function):

    def val2hex(self, val):
        return val

    def format(self, val, addr):
        ans = super().format()
        ans += " [%s] = %s" % (addr, val)
        return str.ljust(ans, 60)

    def _regVCD(self, addr):
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var reg 16 A%d ADDR_%d [15:0] $end\n" % (addr, addr)

    def _dvarVCD(self, val, addr):
        return "%s A%d\n" % (bin(val)[1:], addr)


class Action():

    def __init__(self, fun, val, en=False, br=False, ramp={}, addr=None):
        self.fun = fun
        self.val = val
        self.en = en
        self.br = br
        self.ramp = ramp
        self.addr = addr if addr is not None else self.fun.brd.get_addr(
            self.fun.ch)

    def format(self, sz):
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
        db = isinstance(self.fun.brd, SPBBoards.DO16)
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
    def __init__(self, rel, time, act):
        self.rel = rel
        self.time = time
        self.action = act

    def format(self, sz):
        ts = self.timefmt(self.rel, self.time)
        return str.ljust(ts, 15) + self.action.format(sz - 15)

    def timefmt(self, rel, time):
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
        if self.rel:
            atime += self.time
        else:
            atime = self.time
        return self.action.compile(cval, atime)


class Loop():
    _minDT = 100
    _maxDT = 6840000000000

    def __init__(self, cmt, init, inner, it, en):
        self.cmt = cmt
        self.init = init
        self.inner = inner
        self.it = it
        self.en = en

    def format(self):
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

    def compile(self):
        looplist = []
        cval = {'ids': {}, 'addrs': {}}
        if self.en:
            atime = self._minDT
            for a in self.init:
                if a.en:
                    l = a.compile(cval, atime)
                    if isinstance(a.fun, Test):
                        cval['addrs'][a.addr] = a.val
                    else:
                        cval['ids'][a.fun.ID] = a.val
                    atime += self._minDT
                    looplist.extend(l)
            ln = []
            for a in self.inner:
                if a.action.en:
                    l = a.compile(cval, atime)
                    if isinstance(a.action.fun, Test):
                        cval['addrs'][a.action.addr] = a.action.val
                    else:
                        cval['ids'][a.action.fun.ID] = a.action.val
                    atime = l[0]['abst']
                    ln.extend(l)
                else:
                    atime += l[0]['abst']
            if ln:
                ln.sort(key=lambda v: v['abst'])
                if self.it > 1:
                    ln[0]['first'] = True
                    ln.append({'iter': self.it})
            looplist.extend(ln)

            looplist[0]['relt'] = looplist[0].get('abst') // 100
            i = 1
            n = len(looplist)
            if looplist[-1].get('iter'):
                n -= 1
            while i < n:
                if not looplist[i].get('iter'):
                    if looplist[i].get('first'):
                        dt = looplist[i].get('abst')
                    else:
                        dt = looplist[i].get('abst') - \
                            looplist[i - 1].get('abst')
                    if 0 < dt < self._minDT:
                        raise ValueError('DT too small: %d ns ' % (dt))
                    elif dt == 0:
                        if (looplist[i]['addr'] == looplist[i - 1]['addr']) and looplist[i]['db'] and looplist[i - 1]['db']:
                            looplist[i]['first'] = looplist[i - 1].get('first')
                            looplist[i]['relt'] = looplist[i - 1].get('relt')
                            looplist.pop(i - 1)
                            i -= 1
                            n -= 1
                        else:
                            raise ValueError('Two actions at the same time: %d ns ' % (
                                looplist[i].get('abst')))
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
                else:
                    looplist[i + 1]['relt'] = looplist[i +
                                                       1].get('abst') // 100
                    i += 2
        return looplist
