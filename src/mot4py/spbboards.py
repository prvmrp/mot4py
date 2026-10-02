class SPBBrd():
    """
    superclass for real time boards
    """

    _brdtype = ('Test',
                'DO16',
                'AO1', 'AO4', 'AO8',
                'RF9958', 'RF9958F', 'RF9958LIN',
                'RF9959',
                'RF9912', 'RF9912LIN'
                )

    _vmin = None
    _vmax = None
    _lutmax = None
    _A = None
    _B = None
    _amax = None
    _ch2ofs = {}

    def __init__(self, name, d):
        self.name = name
        self.desc = d.get("desc")
        self.addr = d.get("address")
        self.val = 0

    def get_addr(self, ch):
        return self.addr

    def get_val(self, ch=None):
        if ch is None:
            return self.val
        else:
            return self.val[ch]

    def set_val(self, nv, ch):
        if ch is None:
            self.val = nv
        else:
            self.val[ch] = nv

    def param2val(self, val, ch):
        return val

    def _dac_param2val(self, val):
        val = min(self._vmax, max(self._vmin, val))
        n = int(round(val / (self._vmax - self._vmin) * 0x10000))
        return min(n, 0x7fff)

    def _lut_param2val(self, val):
        if (val <= self._lutmax):
            return val
        else:
            raise ValueError('Invalid LUT index')

    def _lin_param2val(self, val, ch):
        # amp or freq
        if ch[0] == 'A':
            return min(val, self._amax)
        else:
            if isinstance(self.A, tuple):
                i = self._ch2ofs[ch] // 2
                a = self.A[i]
                b = self.B[i]
            else:
                a = self.A
                b = self.B
        n = round((val - a) / b)
        return max(min(n, 0xffff), 0)

    def conn2str(self, ch):
        return ("Brd %s" % (self.name))

    def _lin_conn2str(self, ch):
        return ("Brd %s: Ch. %d" % (self.name, int(ch[1:])))

    def _ch_conn2str(self, ch):
        return ("Brd %s: Ch. %d" % (self.name, int(ch)))

    def _getopt(self, d, opt, default):
        return d.get('opts').get(opt, default) if d.get('opts') else default

    @classmethod
    def genbrd(self, name, d):
        t = d.get('type')
        if t not in self._brdtype:
            raise ValueError('Unknown board type: ' + name)
        else:
            for b in self._brdtype:
                if t == b:
                    return eval(b + '(name, d)')


class Test(SPBBrd):
    def __init__(self, name, d):
        super().__init__(name, d)
        self.ch = 0


class DO16(SPBBrd):

    def __init__(self, name, d):
        super().__init__(name, d)

    def get_val(self, ch):
        mask = 1 << int(ch)
        return self.val & mask != 0

    def set_val(self, nv, ch):
        mask = 1 << int(ch)
        if nv:
            self.val |= mask
        else:
            self.val &= ~mask

    def param2val(self, val, ch):
        self.set_val(val, ch)
        return self.val

    def conn2str(self, ch):
        return ("Brd %s: D%d" % (self.name, int(ch)))


class AO1(SPBBrd):

    _vmin = -10.
    _vmax = 10.

    def __init__(name, d):
        super().__init__(name, d)
        self._vmin = self._getopt(d, 'vmin', AO1._vmin)
        self._vmax = self._getopt(d, 'vmax', AO1._vmax)

    def param2val(self, val, ch):
        return self._dac_param2val(val)


class AO4(SPBBrd):

    _vmin = -10.
    _vmax = 10.
    _lutmax = 2047

    def __init__(self, name, d):
        super().__init__(name, d)
        self._vmin = self._getopt(d, 'vmin', AO4._vmin)
        self._vmax = self._getopt(d, 'vmax', AO4._vmax)
        self._lutmax = AO4._lutmax

    def param2val(self, val, ch):
        return self._lut_param2val(val)

    def conn2str(self, ch):
        return self._ch_conn2str(ch)


class AO8(SPBBrd):

    _vmin = -12.288
    _vmax = 12.288

    def __init__(self, name, d):
        super().__init__(name, d)
        self.val = [0] * 8
        self._vmin = self._getopt(d, 'vmin', AO8._vmin)
        self._vmax = self._getopt(d, 'vmax', AO8._vmax)

    def get_addr(self, ch):
        return self.addr + int(ch)

    def get_val(self, ch):
        return super().get_val(int(ch))

    def set_val(self, nv, ch):
        super().set_val(nv, int(ch))

    def param2val(self, val, ch):
        return self._dac_param2val(val)

    def conn2str(self, ch):
        return self._ch_conn2str(ch)


class RF9958(SPBBrd):

    _lutmax = 1023

    def __init__(self, name, d):
        super().__init__(name, d)
        self._lutmax = RF9958._lutmax

    def param2val(self, val, ch):
        return self._lut_param2val(val)

    def conn2str(self, ch):
        return self._ch_conn2str(ch)


class RF9959(SPBBrd):

    _lutmax = 511

    def __init__(self, name, d):
        super().__init__(name, d)
        self._lutmax = RF9959._lutmax

    def param2val(self, val, ch):
        return self._lut_param2val(val)

    def conn2str(self, ch):
        return self._ch_conn2str(ch)


class RF9958F(SPBBrd):

    _lutmax = 511

    def __init__(self, name, d):
        super().__init__(name, d)
        self._lutmax = RF9958F._lutmax

    def param2val(self, val, ch):
        return self._lut_param2val(val)

    def conn2str(self, ch):
        return self._ch_conn2str(ch)


class RF9912(SPBBrd):

    _lutmax = 2047

    def __init__(self, name, d):
        super().__init__(name, d)
        self._lutmax = RF9912._lutma < x

    def param2val(self, val, ch):
        return self._lut_param2val(val)


class RF9912LIN(SPBBrd):

    _A = 150e6
    _B = 1e3
    _ch2ofs = {'F': 0, 'A': 1}
    _amax = 255
    _lutmax = 65536

    def __init__(self, name, d):
        super().__init__(name, d)
        self.val = [0] * 2
        self.A = self._getopt(d, 'A', RF9912LIN._A)
        self.B = self._getopt(d, 'B', RF9912LIN._B)
        self._amax = RF9912LIN._amax

    def get_addr(self, ch):
        return self.addr + RF9912LIN._ch2ofs.get(ch, 0)

    def get_val(self, ch):
        return super().get_val(RF9912LIN._ch2ofs.get(ch, 0))

    def set_val(self, nv, ch):
        super().set_val(nv, RF9912LIN._ch2ofs.get(ch, 0))

    def param2val(self, val, ch):
        # this is messy and the firmware of the boards should be changed
        if ch[0] == 'A':
            if val > 127:
                val = 0
            else:
                val <<= 1
        return self._lin_param2val(val, ch)


class RF9958LIN(SPBBrd):

    _A = 60e6
    _B = 1e3
    _ch2ofs = {'F0': 0, 'A0': 1, 'F1': 2, 'A1': 3}
    _amax = 1024
    _lutmax = 65536

    def __init__(self, name, d):
        super().__init__(name, d)
        self.val = [0] * 4
        l = self._getopt(d, 'A', RF9958LIN._A)
        if isinstance(l, list):
            self.A = tuple(l)
        else:
            self.A = (l,) * 2
        l = self._getopt(d, 'B', RF9958LIN._B)
        if isinstance(l, list):
            self.B = tuple(l)
        else:
            self.B = (l,) * 2
        self._amax = RF9958LIN._amax

    def get_addr(self, ch):
        return self.addr + RF9958LIN._ch2ofs.get(ch, 0)

    def get_val(self, ch):
        return super().get_val(RF9958LIN._ch2ofs.get(ch, 0))

    def set_val(self, nv, ch):
        super().set_val(nv, RF9958LIN._ch2ofs.get(ch, 0))

    def param2val(self, val, ch):
        return self._lin_param2val(val, ch)

    def conn2str(self, ch):
        return self._lin_conn2str(ch)
