"""
Classes representing a program:
1) Function and its subclasses 
   Simple, Binary, Enum, Scalar and Test;
2) Action and TimedAction;
3) Loop.
"""
from mot4py import spbboards
from mot4py.utils import *


def cMOT_Current(val: float) -> float:
    """
    Converts the current in A to the value in V for Delta Electronika power supply

    args:
         val (float): Current in A

    returns:
            float: to be used as current-programming voltage (here Volt)
    """
    return 0.05*val


def cComp_Coils(val: float) -> float:

    return val / 97.5


def cComp_Freq(val: float, units: str) -> float:
    if units == 'kHz':
        val *= 1.e3
    elif units == 'MHz':
        val *= 1.e6

    return val


class Function():
    """
    Parent class for possible operations in a program.
    Example: Control the B Field MOT switch (On/OFF)

    A Function is defined by:
    name: a str of the form 'board_channel'
          examples:
                  'DO1_7' is digital line 7 on digital output board DO1
                  'AO1_2' is analog output 2 on analog output board AO1
                  'DDS1_F0' is frequency on ch. 0 for DDS board DDS1
    id: a unique int,
    d: a dictionary of options. 
       key : value pairs valid for every Function are
       'desc' : str, short description i.e. 'MOT B Field Switch'
       'type' : str in _funtype, declares Function subclass.   
       other keys depend on board type and channel.

    Everything is defined in 'config.toml'.
    """

    _funtype = ('Simple', 'Binary', 'Enum', 'Scalar', 'Test')

    def __init__(self, name: str, id: int, d: dict, brds: dict):
        self.name = name
        self.ID = id
        self.desc = d.get('desc')
        self.fmt = d.get('fmt')
        self.units = d.get('units')
        self.comp = d.get('compile')
        self.max = d.get('max')
        self.min = d.get('min')
        brd, self.ch = name.split('_')
        self.brd = brds.get(brd)

    @classmethod
    def genfun(self, name: str, id: int, d: dict, brds: dict):
        """
        Calls __init__ for the subclass of Function specified in d['type'].

        args:
            name: func. name
            id: func. id
            d: dictionary of options
            brds: dictionary with all the boards

        returns:
            : Instance of the Function subclass

        raises:
            MOT4PyError: the specified subclass is not known
        """
        t = d.get('type')
        if t not in self._funtype:
            raise MOT4PyError('Unknown function type: ' + name)
            return
        else:
            for b in self._funtype:
                if t == b:
                    return eval(b + '(name, id, d, brds)')

    def __str__(self):
        return self.desc


class Simple(Function):
    """
    Function subclass that does not require any argument.
    The 'compile' key in 'config.toml' is the name of a valid Python
    function in the code returning a uint16 value to be used as data.
    """

    def __init__(self, name: str, id: int, d: dict, brds: dict):
        """
        Initialize a Simple Function.

        raises:
            MOT4PyError: if the key 'compile' is not present in d
        """
        super().__init__(name, id, d, brds)

    def val2hex(self, val, un) -> int:
        """
        Compute the uint16 value to be written on the data bus. 

        args:
            val: ignored
            un: ignored

        returns:
            uint16 as returned by the 'compile' function
            or 0 if 'compile' is not provided 
        """
        if self.comp:
            return eval(self.comp + '()')
        else:
            return 0

    def format(self, val: int, addr: int, units) -> str:
        """
        Emit str for pretty printing.

        args:
            val: ignored
            addr: ignored
            units: ignored

        returns:
            formatted function description
        """
        return str.ljust(super().__str__(), 60)

    def regVCD(self) -> str:
        """
        Emit VCD str for 'register' declaration.
        """
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var wire 1 %d %s $end\n" % (self.ID, name)

    def dvarVCD(self, val: int, addr: int) -> str:
        """
        Emit VCD str for 'value changed' 

        args:
            val: int
            addr: board address, ignored
        """
        return "%d%d\n" % (1 if val else 0, self.ID)


class Binary(Function):
    """
    Function subclass taking a binary argument i.e. On/Off, zero/non zero etc.
    """

    def val2hex(self, val: int, un) -> int:
        """
        Compute the uint16 value to be written on the data bus. 

        args: 
            val: ignored
            un: ignored

        returns:
            uint16 as returned by the 'param2val()' method of the relevant
            board and channel.
        """
        self.brd.set_val(val, self.ch)
        return self.brd.param2val(val, self.ch)

    def format(self, val: int, addr: int, units: str) -> str:
        """
        Emit str for pretty printing.

        args:
            val: int, 0 = Off, else On
            addr: ignored
            units: ignored

        returns:
            formatted function description
        """
        ans = super().__str__()
        ans += " = " + ("On" if val else "Off")
        return str.ljust(ans, 60)

    def regVCD(self) -> str:
        """
        Emit VCD str for 'register' declaration.
        """
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var reg 1 %d %s $end\n" % (self.ID, name)

    def dvarVCD(self, val: int, addr: int) -> str:
        """
        Emit VCD str for 'value changed' 

        args:
            val: int
            addr: board address, ignored
        """
        return "%d%d\n" % (1 if val else 0, self.ID)


class Enum(Function):
    """
    Function subclass taking an integer argument in range(N).
    N depends on board and channel
    """

    def val2hex(self, val: int, un) -> int:
        """
        Compute the uint16 value to be written on the data bus. 

        args:
            val: int <= N
            un: ignored

        returns:
            val as uint16

        raises:
            MOT4PyError: if val > N
        """
        if self.brd._lutmax >= val:
            self.brd.set_val(val, self.ch)
            return val
        else:
            raise MOT4PyError('Invalid state %d for function %s' %
                              (val, self.desc))

    def format(self, val: int, addr: int, units: str) -> str:
        """
        Emit str for pretty printing.

        args:
            val: int
            addr: ignored
            units: ignored

        returns:
            formatted function description
        """
        ans = super().__str__() + (" = [%d]" % (val))
        return str.ljust(ans, 60)

    def regVCD(self) -> str:
        """
        Emit VCD str for 'register' declaration.
        """
        name = self.desc.replace(' ', '_').replace('.', '_')
        if self.max:
            j = self.max.bit_length()
        else:
            j = 16
        return "$var reg %d %d %s [%d:0] $end\n" % (j, self.ID, name, j-1)

    def dvarVCD(self, val: int, addr: int) -> str:
        """
        Emit VCD str for 'value changed' 

        args:
            val: int
            addr: board address, ignored
        """
        return "%s %d\n" % (bin(val)[1:], self.ID)


class Scalar(Function):
    """
    Function subclass taking a float argument. It can use
    hardware (V for Analog Outputs, Hz for DDS Frequencies)
    or physical (i.e. Gamma for frequencies) units.
    In 'config.toml' a str containing the units must be specified
    a str specifying how to format the float value when printing
    is optional. So are min and max limits for the argument.
    """

    def __init__(self, name: str, id: int, d: dict, brds: dict):
        super().__init__(name, id, d, brds)
        if not self.fmt:
            self.fmt = "%.3f%"

    def val2hex(self, val: int, un: str) -> int:
        """
        Compute the uint16 value to be written on the data bus. 
        It can use hardware or physical units. As an example, on
        an Analog Output board, hardware units are Volts and
        the 'param2val()' method for the boards converts Volts
        to uint16 data. If the output controls the current in a coil,
        physical units are Amperes. The 'compile' string specified
        in 'config.toml' must be the name of a valid python function,
        placed in this file, converting Ampere to Volts. This function
        is called before 'param2val()'.

        args:
            val: uint16
            un: str

        returns:
             uint16
        """

        if self.comp:
            v1 = eval(f'{self.comp}({val}, "{un}")')
        else:
            v1 = val
        self.brd.set_val(val, self.ch)
        return self.brd.param2val(v1, self.ch)

    def format(self, val: float, addr: int, units: str) -> str:
        """
        Emit str for pretty printing.

        args:
            val: float
            addr: board address, ignored
            units: units for the current actions

        returns:
            formatted function description
        """
        ans = super().__str__()
        fmt = self.fmt if self.fmt else "%.1f"
        un = " "
        if units:
            un += units
        elif self.units:
            un += self.units
        ans += (" = " + fmt + un) % (val)
        return str.ljust(ans, 60)

    def regVCD(self) -> str:
        """
        Emit VCD str for 'register' declaration.
        """
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var real 64 %d %s $end\n" % (self.ID, name)

    def dvarVCD(self, val: float, addr: int) -> str:
        """
        Emit VCD str for .

        args:
            val: float
            addr: board address, ignored
        """
        return "r%.16g %d\n" % (val, self.ID)


class Test(Function):
    """
    Function subclass taking a uint16 value and an address.
    It is meant for test purposes. It just writes value to
    address without any processing.
    """

    def val2hex(self, val, un) -> int:
        """
        This function just returns its input.
        """
        return val

    def format(self, val: int, addr: int, units: str) -> str:
        """
        Emit str for pretty printing.

        args:
            val: ignored
            un: ignored
            addr: ignored
            units: ignored

        returns:
            formatted function description
        """
        ans = super().__str__()
        ans += " [%s] = %s" % (addr, val)
        return str.ljust(ans, 60)

    def regVCD(self, addr: int) -> str:
        """
        Emit VCD str for 'register' declaration.
        """
        name = self.desc.replace(' ', '_').replace('.', '_')
        return "$var reg 16 A%d ADDR_%d [15:0] $end\n" % (addr, addr)

    def dvarVCD(self, val: int, addr: int) -> str:
        """
        Emit VCD str for .

        args:
            val: int
            addr: int
        """
        return "%s A%d\n" % (bin(val)[1:], addr)


class Action():
    """
    An Action is a sort of instance of a Function. Instructions
    in a program are actions, not functions. Actions have a 
    a specific value but not yet a specific time. An action
    can also describe a 'ramp' i.e. a sequence of instructions
    if the parent Function is of Enum or Scalar type.
    """

    def __init__(self, fun, val, un, en: bool = False, br: bool = False, nop: bool = False, ramp: dict = {}, addr=None):
        self.fun = fun
        self.val = val
        self.units = un
        self.en = en
        self.br = br
        self.nop = nop
        self.ramp = ramp
        self.addr = addr if addr is not None else self.fun.brd.get_addr(
            self.fun.ch)

    def format(self, sz: int) -> str:
        """
        Emit str for pretty printing.

        args:
            sz: int - requested len 

        returns:
            formatted Action description
        """
        if self.ramp:
            if not isinstance(self.fun, (Enum, Scalar)):
                raise MOT4PyError("Invalid ramp for fun %s" % self.fun.desc)
            if self.ramp['log']:
                ans = "RAMPLOG "
            else:
                ans = "RAMP "
            ans += self.fun.format(self.ramp['end'], None,
                                   self.ramp.get('units')).rstrip().replace('=', 'TO', 1)
            ans += " IN %s " % (TimedAction.timefmt(None,
                                False, self.ramp['time']))
            ans += "(%d STEPS) " % self.ramp['steps']
            if len(ans) < sz:
                ans = str.ljust(ans, sz)
        else:
            ans = str.ljust(self.fun.format(
                self.val, self.addr, self.units), sz)
        ans += str.rjust("(%d)" % (self.fun.ID), 6)
        if not self.en:
            ans += " SKIP"
        if self.br:
            ans += " BREAK"
        if self.nop:
            ans += " IDLE"
        ans += '\n'

        return ans

    def _unramp(self, atime: int) -> list[dict]:
        """
        This method unrolls the action if it is ramp.
        It should be called only by the method 'compile()'.
        """
        delta = self.ramp['end'] - self.val
        dt = self.ramp['time'] // self.ramp['steps']
        if self.ramp['log']:
            if self.val != 0:
                ratio = self.ramp['end'] / self.val
                dv = ratio ** (1. / self.ramp['steps'])
            else:
                raise MOT4PyError("log ramp starting from 0\n")
        else:
            dv = delta / self.ramp['steps']
        l = []
        v0 = self.val
        isEnum = isinstance(self.fun, Enum)
        for i in range(self.ramp['steps'] + 1):
            if self.ramp['log']:
                self.val = v0 * (dv ** i)
            else:
                self.val = v0 + dv * i
            if isEnum:
                self.val = int(self.val)
            l.append({'abst': atime, 'val': self.val,
                     'units': self.ramp.get('units')})
            atime += dt
        return l

    def compile(self, cval: dict, atime: int = 0) -> list[dict]:
        """
        Transform an action in a list of dictionaries. This is called
        by Loop.compile() to generate an intermediate representation
        of a program. The list has more than one element only if the action
        is a ramp.

        Each dict in the list has at least the following key : value pairs
        'fun' : parent Function
        'val' : requested value
        'units' : units for scalar actions or None
        'addr': int - board address
        'bin' : uint16 - data to be written on the bus
        'en' : bool - True if the action is enabled
        'br' : bool - True if a breakpoint
        'nop' : bool - True if a nop
        'db' : bool - True if the board is a DO16 
        """
        db = isinstance(self.fun.brd, spbboards.DO16)
        aux = {'addr': self.addr, 'en': self.en,
               'br': self.br, 'nop': self.nop, 'db': db, 'fun': self.fun}
        if not self.ramp:
            hexval = self.fun.val2hex(self.val, self.units)
            return [{'abst': atime, 'val': self.val, 'units': self.units, 'bin': hexval} | aux,]
        else:
            self.val = cval['ids'][self.fun.ID]  # no ramps for Test Actions
            l = self._unramp(atime)
            for e in l:
                hexval = self.fun.val2hex(e['val'], e['units'])
                e |= {'bin': hexval} | aux
            cval['ids'][self.fun.ID] = l[-1]['val']
            return l


class TimedAction():
    """
    A TimeAction is an Action with an associated time,
    either absolute or relative
    """

    def __init__(self, rel: bool, time: int, act):
        self.rel = rel
        self.time = time
        self.action = act

    def format(self, sz: int) -> str:
        """
        Emit str for pretty printing.

        args:
            sz: int - requested len 

        returns:
            formatted TimedAction description
        """
        ts = self.timefmt(self.rel, self.time)
        return str.ljust(ts, 15) + self.action.format(sz - 15)

    def timefmt(self, rel: bool, time: int) -> str:
        """
        Emit str for time (absolute or relative) pretty printing

        args:
            rel: bool - True if relative
            time: int - time in ns

        returns:
            formatted time
        """

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

    def compile(self, cval: dict, atime: int) -> list[dict]:
        """
        See Action.compile()
        """
        if self.rel:
            atime += self.time
        else:
            atime = self.time
        return self.action.compile(cval, atime)


class Loop():
    """
    Class describing a Loop. A loop has the following parts:

    cmt: an opional multiline str for adding comments
    init: a list of actions to be executed once, on consecutive
          bus clock cycle
    inner: a list of action to be executed at the specified times N times
    iterator: an integer specifying N
    enable: a boolean that specifies if the Loop will be executed or skipped.

    At least one between init and (inner + iterator) must be specified
    """
    # interval in INIT between consecutive actions. Use 30us to deal with linear firmware in DDS
    _initDT = 30000
    # min DT in ns. The Bus runs at 10 MHz.
    _minDT = 100
    # max DT in ns, 114 min, an integer number of min. < 100 * 2**36 ns
    _maxDT = 6840_000_000_000

    def __init__(self, cmt: str, init: list[Action], inner: list[TimedAction], it: int, en: bool):
        self.cmt = cmt
        self.init = init
        self.inner = inner
        self.it = it
        self.en = en

    def __str__(self):
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
        """
        Generate an intermediate representation of the program
        as a list of dictionaries.
        - Calls Action.compile() on each element of self.init.
        - Calls TimedAction.compile() on each element of self.inner.
        - Sort according to absolute time.
        - Merges two actions at the same time if they act on bits on the same DO16 board. 
        - Detects actions too close (less than _minDT) by raising an Exception.
        - Silently adds NOP actions if two actions are separated by more than _maxDT.
        - Adds to the first element of Loop.inner the key : value pair 'first' : True.
        - Appends {'iter': n} as last element
        """
        looplist = []
        cval = {'ids': {}, 'addrs': {}}
        if self.en:
            atime = self._initDT
            for a in self.init:
                if a.en:
                    l = a.compile(cval, atime)
                    if isinstance(a.fun, Test):
                        cval['addrs'][a.addr] = a.val
                    else:
                        cval['ids'][a.fun.ID] = a.val
                    atime += self._initDT
                    looplist.extend(l)
            ln = []
            atime = 0
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
                        raise MOT4PyError('DT too small: %d ns ' % (dt))
                    elif dt == 0:
                        if (looplist[i]['addr'] == looplist[i - 1]['addr']) and looplist[i]['db'] and looplist[i - 1]['db']:
                            looplist[i]['first'] = looplist[i - 1].get('first')
                            looplist[i]['relt'] = looplist[i - 1].get('relt')
                            looplist.pop(i - 1)
                            i -= 1
                            n -= 1
                        else:
                            raise MOT4PyError('Two actions at the same time: %d ns ' % (
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
