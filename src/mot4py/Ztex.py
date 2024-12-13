import time
import struct
import usb


class Ztex():

    bufsz = 0xE000000
    memsz = 0x800000
    maxcnt = 0x100000
    vid = 0x221a
    pid = 0x0100
    tmo = 100

    def __init__(self):
        self.exttrg = False
        self.dev = usb.core.find(idVendor=0x221a, idProduct=0x0100)
        if self.dev:
            self.dev.set_configuration()
        self.buf = bytearray()

    def reset(self):
        if self.dev:
            self.softrst()
            self.dev.ctrl_transfer(0x40, 0x31, timeout=self.tmo)
            self.dev.ctrl_transfer(0x40, 0xA0, 0xE600, 0, '\x01', self.tmo)
            time.sleep(0.05)
            self.dev.ctrl_transfer(0x40, 0xA0, 0xE600, 0, '\x00', self.tmo)
            time.sleep(1)
            self.dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
            if self.dev:
                self.dev.set_configuration()

    def softrst(self):
        if self.dev:
            self.dev.write(0x06, 'RS', self.tmo)

    def _dacmd(self, n, a):
        q = ((a['relt'] & 0xFFFFFFFFF) << 24) | (
            (a['bin'] & 0xFFFF) << 8) | ((a['addr'] << 1) & 0xFF)
        if a.get('br'):
            q |= (1 << 60)
        if a.get('nop'):
            q |= (1 << 61)
        self.buf += struct.pack('>2cLQ', b'D', b'A', n & 0xFFFFFFFFF, q)

    def _pack(self, k, l, n=1):
        for i in range(n):
            for a in l:
                self._dacmd(k, a)
                k += 1
        return k

    def start(self):
        if self.dev:
            self.dev.write(0x06, b'TR', self.tmo)

    def set_trg(self):
        if self.dev:
            cmd = b'EX' if self.exttrg else b'IN'
            self.dev.write(0x06, cmd, self.tmo)

    def set(self, addr, data):
        a = {'relt': 10, 'bin': data, 'addr': addr}
        self.buf.clear()
        self._dacmd(0, a)
        self.buf[-8] |= 0x80
        self.buf += b'PLINTR'
        if self.dev:
            self.dev.write(0x06, self.buf, self.tmo)
            time.sleep(0.1)
            self.set_trg()
            self.softrst()
        else:
            self._dump()

    def stop(self):
        if self.dev:
            self.dev.write(0x06, b'HARS', self.tmo)

    def get_stat(self):
        if self.dev:
            self.dev.write(0x06, b'ST', self.tmo)
            ret = self.dev.read(0x82, 4, 20 * self.tmo)
            return chr(ret[0]), (int(ret[1]) << 16) + (int(ret[2]) << 8) + int(ret[3])
        else:
            return 'I', 0

    def get_id(self):
        if self.dev:
            self.dev.write(0x06, b'ID', self.tmo)
            ret = self.dev.read(0x82, 4, self.tmo)
            return (int(ret[1]), int(ret[0])), (int(ret[3]), int(ret[2]))
        else:
            return (1, 0), (1, 0)

    def _dump(self):
        sz = len(self.buf)
        k = 0
        while sz > 14:
            c1, c2, instr, q = struct.unpack('>2cLQ', self.buf[k:k + 14])
            addr = q & 0xFF
            data = (q >> 8) & 0xFFFF
            cnt = (q >> 24) & 0xFFFFFFFFF
            ctrl = (q >> 60) & 0xF
            k += 14
            sz -= 14
            print('cmd = %s, mem. addr = %d, ctrl = %s, cnt = %d, data = %s, addr = %s' % (
                (c1+c2).decode(), instr, hex(ctrl), cnt, hex(data), hex(addr >> 1)))
        print('cmd = %s' % self.buf[k:].decode())

    def load(self, prog):
        if prog.len > self.maxcnt:
            raise ValueError(
                "Program too long (%d instr. vs. %d max)" % (prog.len, self.maxcnt))
        else:
            self.set_trg()
            self.buf.clear()
            addr = 0
            for l in prog.compiled:
                n = l[-1].get('iter')
                if n:
                    for k, a in enumerate(l):
                        if a.get('first'):
                            break
                    f = k
                    addr = self._pack(addr, l[0:k])  # init
                    addr = self._pack(addr, l[k:-1], n)  # inner
                else:
                    addr = self._pack(addr, l)  # only init
            self.buf[-8] |= 0x80
            self.buf += b'PLTR'
            sz = len(self.buf)
            k = 0
            if self.dev:
                while sz > self.bufsz:
                    self.dev.write(0x06, self.buf[k:k + sz], 10 * self.tmo)
                    sz -= self.bufsz
                    k += self.bufsz
                self.dev.write(0x06, self.buf[k:], 10 * self.tmo)
            else:
                self._dump()
