import sys, signal, argparse, os, psutil, tempfile, usb
from importlib.resources import files

if sys.version_info.minor < 11:
    import toml
else:
    import tomllib

from lark import Lark, visitors

from PyQt5 import Qt, QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtRemoveInputHook        

from .SPBBoards import SPBBrd
from .Ztex import Ztex
from .Functions import *
from .Parser import *

def parseconfig(fname):
    if sys.version_info.minor < 11:
        config = toml.load(fname)
    else:
        with open(fname, "rb") as f:
            config = tomllib.load(f)
    #parse Boards
    Boards = {}
    for n, d in config.pop('Board').items():
        try:
            Boards[n]=SPBBrd.genbrd(n, d)
        except ValueError as err:
            error(err.args[0])
    #gen. IDs
    IDdict = {}
    for n, d in config.pop('ID').items():
        brd, ch = n.split('_')
        if ch in ['rng', 'lst']:
            if ch == 'rng':
                l1 = list(range(d[0][0],d[0][1] + 1))
                fmt = '%s_%s'
            else:
                l1 = d[0]
                fmt = '%s_%s'
            l2 = list(range(d[1][0],d[1][1] + 1))
            for i in range(len(l1)):
                IDdict[fmt % (brd, l1[i])] = l2[i]
        else:
            IDdict[n] = d
    #Add Test
    Boards['Test'] = SPBBrd.genbrd('Test', {'desc':'Fake test board', 'type':'Test', 'address':128})
    IDdict['Test_Test'] = 1000
    IDrev = dict([reversed(i) for i in IDdict.items()])
    #parse functions
    Fundict = {}
    for n, d in config.pop('SPB').items():        
        if n in IDdict.keys():
            Fundict[n] = Function.genfun(n, IDdict[n], d, Boards)
        else:
            error('Function without ID: ' + n)
    #Add Test
    d = {'desc':'Test Function', 'type':'Test'}
    n = 'Test_Test'
    Fundict[n] = Function.genfun(n, IDdict[n], d, Boards)
    return Boards, IDdict, IDrev, Fundict

def hsconncb(show):
    if mainwin.sender() == connwin.closebt:
        connwin.hide()
    else:
        connwin.show()

def hscodecb(show):
    if mainwin.sender() == codewin.closebt:
        codewin.hide()
    else:
        codewin.show()

def aboutcb():
    QtWidgets.QMessageBox.about(
        mainwin, 'MOT4 in Python',
        'Send complaints to\n  marco.prevedelli@unibo.it')

def savecb():
    if state['prog']:    
        fn = QtWidgets.QFileDialog.getSaveFileName(mainwin, 'Save As ..', '', (
           'Mor files (*.mot);;All files (*)'))[0]
        if fn:
            with open(fn, 'w') as file:
                file.write(prog.format())
                file.close()
            mainwin.statusbar.showMessage("Prog. saved", 0)

def loadcb():
    global prog, state

    fn = QtWidgets.QFileDialog.getOpenFileName(mainwin, 'Open ..', '', (
        'Mot files (*.mot);;All files (*)'))[0]
    
    if fn:
        try:
            prog = Parser(fn, Fundict)
        except ValueError as err:
            error(err.args[0])
        state['prog'] = fn
        update()
        mainwin.statusbar.showMessage("Prog. loaded", 0)

def VCDcb():
    prog.wrVCD()
    mainwin.statusbar.showMessage("VCD file(s) saved", 0)

def reloadcb():
    global prog
    
    if state['prog']:
        prog = Parser(state['prog'], Fundict)
        mainwin.statusbar.showMessage("Prog. reloaded", 0)

def _run():
    global state
    
    if state['prog']:
        try:
            fpga.softrst()
            fpga.load(prog)
            fpga.start()
        except ValueError as err:
            error(err.args[0])
        state['run'] = True
        if not state['gui']:
            while state['run']:
                time.sleep(1)
                getstatcb()
            

def getstatcb():
    global state

    s, n = fpga.get_stat()
    if s == 'I':
        msg = 'Idle'
    elif s == 'W':
        msg = 'Waiting for Trigger'
    elif s == 'R': 
        msg = "Running at Instr. %d of %d" % (n, prog.len)
    elif s == 'B': 
        msg = "Breakpoint at Instr. %d" % (n,)
    elif s == 'E':
        msg = 'Prog. ended'
    else:
        msg = 'Unkown FPGA code'
    if s in ('I', 'E'):
        if state['gui']:
            timer.stop()
        state['run'] = False
    if state['gui']:
        update()
        mainwin.statusbar.showMessage(msg, 0)
    else:
        print(msg)
        
def runcb():
    _run()
    mainwin.statusbar.showMessage('Prog. running', 0)
    timer.start()
    update()

def resetcb():    
    fpga.reset()
    if state['gui']:
        msg = "FPGA reset" if fpga.dev else "FPGA not found"
        mainwin.statusbar.showMessage(msg, 0)
            
def stopcb():
    global state
    
    fpga.stop()
    timer.stop()
    state['run'] = False
    mainwin.statusbar.showMessage('Prog. stopped', 0)    
    update()

def testcb():
    testwin.show()
        
def quitcb():
    if state['run']:
        stopcb()
    os.unlink(lockfile)
    exit()    

def update():    
    mainwin.actionLoad.setEnabled(not state['run'])
    mainwin.reloadbt.setEnabled(state['prog'] is not None and not state['run'])
    mainwin.actionReload.setEnabled(state['prog'] is not None and not state['run'])
    mainwin.actionSave.setEnabled(state['prog'] is not None)
    mainwin.actionWrite_VCD.setEnabled(state['prog'] is not None)
    mainwin.runbt.setEnabled(state['prog'] is not None and not state['run'])
    mainwin.actionRun.setEnabled(state['prog'] is not None and not state['run'])
    mainwin.stopbt.setEnabled(state['run'])
    mainwin.actionStop.setEnabled(state['run'])
    mainwin.testbt.setEnabled(not state['run'])
    mainwin.actionTest.setEnabled(not state['run'])
    mainwin.resetbt.setEnabled(not state['run'])
    
def error(msg):
    if state['gui']:
        QtWidgets.QMessageBox.critical(mainwin, 'Error', msg)
        exit()
    else:
        exit(msg)
    
class TableWin(QtWidgets.QWidget): 
    def __init__(self, title, hdr, data): 
        super().__init__() 
        self.title = title
        self.setWindowTitle(self.title)
        self.setWindowIcon(Qt.QIcon("icons/trap.pbm"))
        self.createTable(hdr, data)
        self.addButtons() 
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.tableWidget)
        self.layout.addWidget(self.ButtonBox)
        self.setLayout(self.layout)
        self.adjustSize()
   
    def createTable(self, hdr, data): 
        self.tableWidget = QtWidgets.QTableWidget() 
        self.tableWidget.setRowCount(len(data))  
        self.tableWidget.setColumnCount(len(hdr))
        self.tableWidget.setAlternatingRowColors(True)
        self.tableWidget.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.tableWidget.setHorizontalHeaderLabels(hdr)
        self.tableWidget.setVerticalHeaderLabels((None, ) * len(data))
        for i, d in enumerate(data):
            for j, p in enumerate(d):
                self.tableWidget.setItem(i, j, QtWidgets.QTableWidgetItem(p))
        self.tableWidget.resizeColumnsToContents()

    def addButtons(self):
        self.ButtonBox = QtWidgets.QDialogButtonBox(QtCore.Qt.Horizontal)
        self.closebt = self.ButtonBox.addButton(QtWidgets.QDialogButtonBox.Close)
        self.ButtonBox.setCenterButtons(True)

class TestBinary(QtWidgets.QWidget): 
    def __init__(self): 
        super().__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.bb = QtWidgets.QCheckBox('On')
        self.layout.addWidget(self.bb)
        self.layout.setAlignment(QtCore.Qt.AlignCenter)
        self.setLayout(self.layout)

    def setval(self, val):
        self.bb.setChecked(val)

    def getval(self):
        return self.bb.checkState()
        
class TestEnum(QtWidgets.QWidget): 
    def __init__(self): 
        super().__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.spb = QtWidgets.QSpinBox()
        self.layout.addWidget(self.spb)
        self.layout.setAlignment(QtCore.Qt.AlignCenter)
        self.setLayout(self.layout)

    def setval(self, val):
        self.spb.setValue(val)
        
    def setrange(self, min, max):
        self.spb.setRange(min, max)
        
    def getval(self):
        return self.spb.value()
        
class TestSingle(QtWidgets.QWidget): 
    def __init__(self): 
        super().__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.spb = QtWidgets.QDoubleSpinBox()
        self.lab = QtWidgets.QLabel('A.U.')
        self.layout.addWidget(self.spb)
        self.layout.addWidget(self.lab)
        self.layout.setAlignment(QtCore.Qt.AlignCenter)
        self.setLayout(self.layout)

    def setval(self, val):
        self.spb.setValue(val)
        
    def setrange(self, min, max):
        self.spb.setRange(min, max)

    def setunits(self, un):
        self.lab.setText(un)

    def getval(self):
        return self.spb.value()
        
class TestTest(QtWidgets.QWidget): 
    def __init__(self): 
        super().__init__()
        self.layout = QtWidgets.QHBoxLayout()
        self.addrspb = QtWidgets.QSpinBox()
        self.addrlab = QtWidgets.QLabel('Addr.')
        self.valspb = QtWidgets.QSpinBox()
        self.vallab = QtWidgets.QLabel('Value')
        self.addrspb.setRange(0, 127)
        self.valspb.setRange(0, 65535)
        self.layout.addWidget(self.addrspb)
        self.layout.addWidget(self.addrlab)
        self.layout.addWidget(self.valspb)
        self.layout.addWidget(self.vallab)
        self.layout.setAlignment(QtCore.Qt.AlignCenter)
        self.setLayout(self.layout)

    def setval(self, val):
        self.valspb.setValue(val)
        
    def setaddr(self, addr):
        self.addrspb.setValue(addr)

    def getval(self):
        return self.valspb.value()

    def getaddr(self):
        return self.addrspb.value()
        
class TestWin(QtWidgets.QWidget): 
    def __init__(self, fundict): 
        super().__init__()
        self.fd = {}
        self.setWindowTitle('Test')
        self.setWindowIcon(Qt.QIcon("icons/trap.pbm"))
        self.createComboBox(fundict)
        self.ComboBox.activated.connect(self.setindexcb)
        self.createStack()
        self.setindexcb(self.ComboBox.currentIndex())
        self.addButtons() 
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(QtWidgets.QLabel('Action'))
        self.layout.addWidget(self.ComboBox)
        self.layout.addLayout(self.Stack)
        self.layout.addWidget(self.ButtonBox)
        self.setLayout(self.layout)
        self.adjustSize()
        self.closebt.clicked.connect(self.closecb)
        self.runbt.clicked.connect(self.runcb)

    def closecb(self):
        self.hide()
        
    def runcb(self):
        i = self.ComboBox.currentIndex()
        if isinstance(self.fd[i], Simple):
            addr = self.fd[i].brd.get_addr(self.fd[i].ch)
            val = self.fd[i].brd.get_val(self.fd[i].ch)
        elif isinstance(self.fd[i], Binary):
            addr = self.fd[i].brd.get_addr(self.fd[i].ch)
            val = self.fd[i].val2hex(self.stackbin.getval())
        elif isinstance(self.fd[i], Enum):
            addr = self.fd[i].brd.get_addr(self.fd[i].ch)
            val = self.fd[i].val2hex(self.stackenum.getval())
        elif isinstance(self.fd[i], Scalar):
            addr = self.fd[i].brd.get_addr(self.fd[i].ch)
            val = self.fd[i].val2hex(self.stackscalar.getval())
        elif isinstance(self.fd[i], Test):
            addr = self.stacktest.getaddr()
            val = self.stacktest.getval()            
        fpga.set(addr, val)
        
    def createComboBox(self, fundict): 
        self.ComboBox = QtWidgets.QComboBox() 
        for i, v in enumerate(fundict.values()):
            self.ComboBox.addItem(v.desc)
            self.fd[i] = v
            
    def createStack(self): 
        self.Stack = QtWidgets.QStackedLayout()
        self.stacksimp = QtWidgets.QWidget()
        self.stackbin = TestBinary()
        self.stackenum = TestEnum()
        self.stackscalar = TestSingle()
        self.stacktest = TestTest()
        self.Stack.addWidget(self.stacksimp)
        self.Stack.addWidget(self.stackbin)
        self.Stack.addWidget(self.stackenum)
        self.Stack.addWidget(self.stackscalar)
        self.Stack.addWidget(self.stacktest)
            
    def addButtons(self):
        self.ButtonBox = QtWidgets.QDialogButtonBox(QtCore.Qt.Horizontal)
        self.closebt = self.ButtonBox.addButton(QtWidgets.QDialogButtonBox.Close)
        self.runbt = self.ButtonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.ButtonBox.setCenterButtons(True)

    def setindexcb(self, i):
        val = 0
        if isinstance(self.fd[i], Simple):
            val = 0
        elif isinstance(self.fd[i], Binary):
            val = 1
            self.stackbin.setval(self.fd[i].brd.get_val(self.fd[i].ch))
        elif isinstance(self.fd[i], Enum):
            val = 2
            self.stackenum.setval(self.fd[i].brd.get_val(self.fd[i].ch))
            if None not in (self.fd[i].min, self.fd[i].max):
                self.stackenum.setrange(self.fd[i].min, self.fd[i].max)                
        elif isinstance(self.fd[i], Scalar):
            val = 3
            self.stackscalar.setval(self.fd[i].brd.get_val(self.fd[i].ch))
            self.stackscalar.setunits(self.fd[i].units)
            if None not in (self.fd[i].min, self.fd[i].max):
                self.stackscalar.setrange(self.fd[i].min, self.fd[i].max)
        elif isinstance(self.fd[i], Test):
            val = 4
            self.stacktest.setaddr(0)
            self.stacktest.setval(0)
        self.Stack.setCurrentIndex(val)        
        

def main():
    global lockfile, prog, state, fpga
    state = {'gui':False, 'prog':None, 'run':False}

    #find if another instance is running
    lockfile = tempfile.gettempdir() + '/mot4.pid'
    try:
        pid = int(open(lockfile, 'r').read())
        if psutil.pid_exists(pid):
            exit('Program is already running with PID %d\n' % (pid))
        else:
            raise FileNotFoundError('Delete stale lock file') 
    except FileNotFoundError:
        with open(lockfile, 'w') as f:
            f.write(str(os.getpid()))

    signal.signal(signal.SIGINT, quitcb)
            
    config_file = files("mot4py.config").joinpath("config.toml")
    Boards, IDdict, IDrev, Fundict = parseconfig(config_file)
    #check for overlapping addresses
    err = False
    l = [0] * 129
    for v in Boards.values():
        if isinstance(v.val, list):
            for i in range(len(v.val)):
                l[v.addr + i] += 1
        else:
            l[v.addr] += 1
    for k, i in enumerate(l):
        if i > 1:
            print('Conflict: %d boards claim address %d' % (i, k))
            err = True
    if err:
        exit()
    #check for duplicate codes
    if len(list(IDdict.values())) > len(set(IDdict.values())):
        exit('Duplicate IDs defined in config file')
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='Run directly a mot file without GUI ', dest='fname')
    parser.add_argument('-R', '--reset', help='just reset FPGA and quit', action='store_true')
    parser.add_argument('-e', '--exttrg', help='External Trigger mode', action='store_true')
    parser.add_argument('-i', '--info', help='Print FPGA info then quit', action='store_true')

    args = parser.parse_args()

    fpga = Ztex()
    if fpga.dev:
        fpga.exttrg = args.exttrg
        fpga.set_trg()

    if args.info:
        state['gui'] = False
        fwver, brdver = fpga.get_id()
        print('Firmware Ver. %d.%d' % fwver)
        print('Board Num. %d.%d' % brdver)
        exit()
            
    if args.fname is not None:
        state['gui'] = False
        prog = Parser(args.fname, Fundict)
        state['prog'] = args.fname
        if not fpga.dev:
            error('FPGA not found!')
        else:
            _run()
        exit()
    elif args.reset:
        resetcb()
        exit()
    else:
        state['gui'] = True

    if state['gui']:        
        app = QtWidgets.QApplication(sys.argv)
        app.setStyle('Fusion')

        timer = Qt.QTimer()
        timer.setInterval(1000)
        timer.timeout.connect(getstatcb)

        # load the ui configuration files
        ui_file = files("mot4py.resources").joinpath("mot4qt.ui")
        mainwin = uic.loadUi(ui_file)
        w = mainwin.horizontalLayout.sizeHint().width() + 2
        h = mainwin.horizontalLayout.sizeHint().height() + mainwin.menubar.sizeHint().height() + mainwin.statusbar.sizeHint().height() + 2
        mainwin.setFixedSize(QtCore.QSize(w, h))
        update()
        mainwin.show()
        mainwin.statusbar.showMessage("Idle", 0)

        #connections
        conndata = []
        for f in Fundict.values():
            if f.brd and not isinstance(f.brd, SPBBoards.Test):
                conndata.append((f.desc, f.brd.conn2str(f.ch), str(f.ID)))
        connwin = TableWin('Conn. Table', ('Function', 'Connection', 'Code'), conndata)
        mainwin.actionConnections.triggered.connect(hsconncb)
        connwin.closebt.clicked.connect(hsconncb)

        #codes
        codedata = []
        for k, n in IDdict.items():
            brd, ch = k.split('_')
            if brd == 'Test':
                codedata.append((brd, str(n)))
            else:
                codedata.append((Boards[brd].conn2str(ch), str(n)))
        codewin = TableWin('Codes', ('Function', 'Code'), codedata)
        codewin.closebt.clicked.connect(hscodecb)
        mainwin.actionCodes.triggered.connect(hscodecb)

        #test
        testwin = TestWin(Fundict)
        mainwin.testbt.clicked.connect(testcb)
        mainwin.actionTest.triggered.connect(testcb)
        
        #about
        mainwin.actionAbout.triggered.connect(aboutcb)

        #menu
        mainwin.actionLoad.triggered.connect(loadcb)
        mainwin.actionSave.triggered.connect(savecb)
        mainwin.actionReload.triggered.connect(reloadcb)
        mainwin.reloadbt.clicked.connect(reloadcb)
        mainwin.actionWrite_VCD.triggered.connect(VCDcb)
        mainwin.actionRun.triggered.connect(runcb)
        mainwin.runbt.clicked.connect(runcb)
        mainwin.actionStop.triggered.connect(stopcb)
        mainwin.stopbt.clicked.connect(stopcb)
        mainwin.actionQuit.triggered.connect(quitcb)
        mainwin.resetbt.clicked.connect(resetcb)
        
        # start the app
        app.exec()

if __name__ == "__main__":
    main()
