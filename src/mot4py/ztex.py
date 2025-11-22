import struct
import time

import usb

from mot4py.functions import *
from mot4py.utils import *


class Ztex():

    mem2_04 = 0x800000
    mem2_13 = 0x10000000
    vid = 0x221a
    pid = 0x0100
    tmo = 100

    def __init__(self, debug: bool):
        self.debug = debug
        self.exttrg = False
        self.dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
        if self.dev:
            if self.dev.is_kernel_driver_active(1):
                self.dev.detach_kernel_driver_active(1)
            self.dev.set_configuration()
        fw, brd = self.get_id()
        if brd in ((2, 13), (2, 12)):
            self.maxcnt = self.mem2_13
            self.large = True
            self.bufsz = 22 << 18
        else:
            self.maxcnt = self.mem2_04
            self.large = False
            self.bufsz = 14 << 18
        self.buf = bytearray()

    def reset(self) -> None:
        if self.dev:
            self.dev.ctrl_transfer(0x40, 0x31, timeout=self.tmo)
            self.dev.ctrl_transfer(0x40, 0xA0, 0xE600, 0, '\x01', self.tmo)
            time.sleep(0.05)
            self.dev.ctrl_transfer(0x40, 0xA0, 0xE600, 0, '\x00', self.tmo)
            time.sleep(1)
            self.dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
            if self.dev:
                if self.dev.is_kernel_driver_active(1):
                    self.dev.detach_kernel_driver_active(1)
                self.dev.set_configuration()

    def softrst(self) -> None:
        if self.dev:
            self.dev.write(0x06, 'RS', self.tmo)
            time.sleep(1)

    def _dacmd(self, n, a):
        q = ((a['relt'] & 0xFFFFFFFFF) << 24) | (
            (a['bin'] & 0xFFFF) << 8) | ((a['addr'] << 1) & 0xFF)
        if a.get('br'):
            q |= (1 << 60)
        if a.get('nop'):
            q |= (1 << 61)
        self.buf += struct.pack('>2cLQ', b'D', b'A', n & 0xFFFFFFFF, q)

    def _d2cmd(self, n, a, b):
        qa = ((a['relt'] & 0xFFFFFFFFF) << 24) | (
            (a['bin'] & 0xFFFF) << 8) | ((a['addr'] << 1) & 0xFF)
        if a.get('br'):
            qa |= (1 << 60)
        if a.get('nop'):
            qa |= (1 << 61)
        qb = ((b['relt'] & 0xFFFFFFFFF) << 24) | (
            (b['bin'] & 0xFFFF) << 8) | ((b['addr'] << 1) & 0xFF)
        if b.get('br'):
            qb |= (1 << 60)
        if b.get('nop'):
            qb |= (1 << 61)
        self.buf += struct.pack('>2cL2Q', b'D', b'2', n & 0xFFFFFFFF, qb, qa)

    def _pack(self, k, l, n=1):

        global packa2, packaddr

        if k == 0:
            packaddr = 1
        for i in range(n):
            for a in l:
                if self.large:
                    if k % 2:
                        self._d2cmd(packaddr, packa2, a)
                        packaddr += 1
                    else:
                        packa2 = a
                else:
                    self._dacmd(k, a)
                k += 1
        return k

    def start(self) -> None:
        if self.dev:
            self.dev.write(0x06, b'TR', self.tmo)
        else:
            if not self.debug:
                raise MOT4PyError("FPGA not found")

    def set_trg(self) -> None:
        if self.dev:
            cmd = b'EX' if self.exttrg else b'IN'
            self.dev.write(0x06, cmd, self.tmo)

    def set(self, addr: int, data: int) -> None:
        a = {'relt': 10, 'bin': data, 'addr': addr}
        self.buf.clear()
        if self.large:
            self._d2cmd(1, a, {'relt': 10, 'bin': 0, 'addr': 0, 'nop': True})
            self.buf[-16] |= 0x80
        else:
            self._dacmd(0, a)
            self.buf[-8] |= 0x80
        self.buf += b'PLINTR'
        if self.dev:
            self.dev.write(0x06, self.buf, self.tmo)
            time.sleep(0.1)
            self.set_trg()
        else:
            if self.debug:
                self._dump()

    def stop(self) -> None:
        if self.dev:
            self.dev.write(0x06, b'HA', self.tmo)

    def get_stat(self) -> tuple:
        if self.dev:
            self.dev.write(0x06, b'ST', self.tmo)
            ret = self.dev.read(0x82, 4, 20 * self.tmo)
            return chr(ret[0] & 0x7f), (int(ret[0] & 0x80) << 17) + (int(ret[1]) << 16) + (int(ret[2]) << 8) + int(ret[3])
        else:
            return 'I', 0

    def get_id(self) -> tuple:
        if self.dev:
            ret = self.dev.write(0x06, b'ID', self.tmo)
            ret = self.dev.read(0x82, 4, self.tmo)
            return (int(ret[0]), int(ret[1])), (int(ret[2]), int(ret[3]))
        else:
            return (1, 0), (2, 4)

    def _dump(self) -> None:
        sz = len(self.buf)
        k = 0
        if self.large:
            while sz > 22:
                c1, c2, instr, q1, q2 = struct.unpack(
                    '>2cL2Q', self.buf[k:k + 22])
                addr1 = q1 & 0xFF
                data1 = (q1 >> 8) & 0xFFFF
                cnt1 = (q1 >> 24) & 0xFFFFFFFFF
                ctrl1 = (q1 >> 60) & 0xF
                addr2 = q2 & 0xFF
                data2 = (q2 >> 8) & 0xFFFF
                cnt2 = (q2 >> 24) & 0xFFFFFFFFF
                ctrl2 = (q2 >> 60) & 0xF
                k += 22
                sz -= 22
                print('cmd = %s, mem. addr = %d' % ((c1+c2).decode(), instr))
                print('     ctrl1 = %s, cnt1 = %d, data1 = %s, addr1 = %s' %
                      (hex(ctrl1), cnt1, hex(data1), hex(addr1 >> 1)))
                print('     ctrl2 = %s, cnt2 = %d, data2 = %s, addr2 = %s' %
                      (hex(ctrl2), cnt2, hex(data2), hex(addr2 >> 1)))
            print('cmd = %s' % self.buf[k:].decode())
        else:
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

    def load(self, proglist: list, proglen: int) -> None:
        if proglen > self.maxcnt:
            raise MOT4PyError(
                "Program too long (%d instr. vs. %d max)" % (prog.len, self.maxcnt))
        else:
            if self.large:
                if proglen % 2:
                    proglist.append(
                        [{'relt': 10, 'bin': 0, 'addr': 0, 'nop': True},])
                    dummy = True
                else:
                    dummy = False
            self.set_trg()
            self.buf.clear()
            addr = 0
            for l in proglist:
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
            if self.large and dummy:
                self.buf[-16] |= 0x80
            else:
                self.buf[-8] |= 0x80
            self.buf += b'PL'
            sz = len(self.buf)
            k = 0
            if self.debug:
                self._dump()
            else:
                if self.dev:
                    while sz > self.bufsz:
                        self.dev.write(
                            0x06, self.buf[k:k + self.bufsz], 100 * self.tmo)
                        sz -= self.bufsz
                        k += self.bufsz
                    self.dev.write(0x06, self.buf[k:], 100 * self.tmo)
