import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore
import sys  # We need sys so that we can pass argv to QApplication
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from queue import Queue
import time

from Saving_final import DataSave
from EMGThread import EMGThread
import globalvar as gl


class M1Thread(QThread):
    signal = pyqtSignal('PyQt_PyObject')

    def __init__(self, function, in_q, in_EMG, fs, nch, pd):
        QThread.__init__(self)
        print('initialize the m1 thread')
        #### Use the M1 thread input ####
        self.callback = function    # Get current data by update plot function
        self.In = in_q              # Get the EMG counter from queue
        self.InEMG = in_EMG         # Get the raw EMG from queue

        #### Other Init ####
        self.mode = 0                   # Mode selection init
        self.trig = 0                   # Trigger count init
        self.timenow = 0                # Flag for time init
        self.All_queue = Queue()        # Queue for saving
        self.fs = fs                    # Sampling frequency
        self.status = 1                 # Flag for start/stop status init
        self.nch = nch                  # Number of analog channels to read
        self.pd = pd                    # Plot duration (seconds)

        self.EMGList = [None] * self.nch
        for x in range(0, self.nch):
            self.EMGList[x] = [0] * self.pd * self.fs

    def setmode(self, mode):
        print('set mode')
        self.mode = mode

    def stopM1(self):
        self.status = 1
        print('Stop')

    def startM1(self):
        self.status = 2
        print('Start')

    # run method gets called when we start the thread
    def run(self):
        while True:
            ########################
            #### EMG processing ####
            ########################
            #### 1. Get raw EMG data & timer ####
            checkingpoint = self.In.get()

            EMGRaw = [0] * self.nch
            for x in range(0, self.nch):
                EMGRaw[x] = self.InEMG.get()

            for x in range(0, self.nch):
                self.EMGList[x] = self.EMGList[x][1:]
                self.EMGList[x].append(EMGRaw[x][0])

            ###########################################################
            #### M1 thread, use checkingpoint as syncronized timer ####
            ###########################################################

            if checkingpoint == round(self.fs/100):  # self.fs/100, within loop self.fs/10
                # #### Moving average, moving step = checkingpoint ####
                #### Mode selection ####
                if self.mode == 1 or self.mode == 0:  # Visual feedback mode + Recording mode
                    target = self.callback(self.EMGList)


            #####################
            #### Data saving ####
            #####################
            # Will be saved to csv file. To save additional variables, add below and change DataSave in MainWindow
            self.All_queue.put(self.timenow)
            for x in range(0, self.nch):
                self.All_queue.put(EMGRaw[x])

            #### Update Time ####
            self.timenow = self.timenow + 1/self.fs

        print("Exit run")


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setGeometry(500, 100, 985, 900)
        self.plot = False
        self.fs = 1500
        self.nch = 9  # should be odd number for designed plot colors (max is 9; 4x2 emg + trigger)
        self.pd = 3
        self.space = 1.5  # space (in V) between channels on plot

        ###########################
        ######  GUI Design   ######
        ###########################

        ####### Line 0 (Graph plot) ########
        self.graphWidget = pg.PlotWidget()

        # Add Background colour to white
        self.graphWidget.setBackground('w')
        self.graphWidget.setTitle("Dyad EMG")
        self.graphWidget.setLabel('left', 'Magnitude (V)', color='red', size=30)
        self.graphWidget.setLabel('bottom', 'Samples', color='red', size=30)
        # self.graphWidget.addLegend()
        self.graphWidget.showGrid(x=True, y=True)

        self.lh0 = QtWidgets.QHBoxLayout()
        self.lh0.addWidget(self.graphWidget)
        self.h_wid0 = QtWidgets.QWidget()
        self.h_wid0.setLayout(self.lh0)

        ####### Line 1 ########
        self.btn_connect = QtWidgets.QPushButton('Connect')
        self.btn_connect.clicked.connect(self.connectemg)

        self.cbmode = QtWidgets.QComboBox()
        self.cbmode.addItem("Recording Mode")
        self.cbmode.addItem("Visual Feedback Mode")
        self.cbmode.currentIndexChanged.connect(self.modechange)

        self.btn_start = QtWidgets.QPushButton('Start')
        self.btn_start.clicked.connect(self.start)
        self.btn_start.setDisabled(True)

        self.btn_Exit = QtWidgets.QPushButton('Exit')
        self.btn_Exit.clicked.connect(self.Exit)
        self.btn_Exit.setDisabled(True)

        self.lh1 = QtWidgets.QHBoxLayout()
        self.lh1.addWidget(self.btn_connect)
        self.lh1.addWidget(self.cbmode)
        self.lh1.addWidget(self.btn_start)
        self.lh1.addWidget(self.btn_Exit)
        self.h_wid1 = QtWidgets.QWidget()
        self.h_wid1.setLayout(self.lh1)

        ####### Line 2 ########

        self.cbChan = QtWidgets.QComboBox()
        self.cbChan.addItem("All EMG")
        for x in range(0, self.nch):
            self.cbChan.addItem(("EMG" + str(x+1)))
        self.cbChan.currentIndexChanged.connect(self.chanchange)

        self.btn_Saving = QtWidgets.QPushButton("Start Sampling!")
        self.btn_Saving.clicked.connect(self.Saving)
        self.btn_Saving.setDisabled(False)

        self.lh2 = QtWidgets.QHBoxLayout()
        self.lh2.addWidget(self.cbChan)
        self.lh2.addWidget(self.btn_Saving)
        self.h_wid2 = QtWidgets.QWidget()
        self.h_wid2.setLayout(self.lh2)

        # create layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.h_wid0)
        layout.addWidget(self.h_wid1)
        layout.addWidget(self.h_wid2)

        # add layout to widget and display
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        
        #### ComboBox Init ####
        self.Chanmode = 0  # Channel, 0 = All, 1-(number of channels-1) = EMG, (number of channels) = trigger
        self.mode = 0  # Mode selection, 0 = Recording mode, 1 = Visual feedback mode

        #### Status Init ####
        self.status = 0  # Connection status, 0 = Not Connected, 1 = Connected and start, 2 = Connected and stop
        self.Savingstatus = 1  # Saving status, 1 = Start saving, 2 = Stop saving

        #### Queue Init ####
        # Use Queue to send data from EMG thread to M1 thread. MainWindow (GUI thread) to coordinate.
        self.check = Queue()   # Timer(Counter) to synchronize M1 and EMG thread
        self.EMGQ = Queue()    # Raw EMG (2 x number of emg channels, trigger channel for synchronization with M1)

        #### Plot Init ####
        self.plot_init = 0
        self.plot_counter = 0   # This is used to set FPS of plotting
        self.init_dynamic_plot()

    ##########################################################
    #### Line1: Functions about connection and start/exit ####
    ##########################################################
    def connectemg(self):
        if self.status == 0:
            self.status = 1

            #### EMG connection ####
            try:
                self.EMGthread = EMGThread(self.check, self.EMGQ, self.fs, self.nch)
                print("EMG Connected!")
            except:
                print('No EMG Connection! Please check and restart.')    # If No EMG connection, the system will not work.

            #### M1 thread connection ####
            self.m1thread = M1Thread(self.update_plot, self.check, self.EMGQ, self.fs, self.nch, self.pd)
            self.m1thread.setmode(self.mode)

            #### Button activation ####
            self.btn_connect.setDisabled(True)
            self.btn_start.setDisabled(False)
            self.btn_Exit.setDisabled(False)

            print("Connect emg!")

    def start(self):
        if self.status == 1:
            #### Start M1 and EMG thread ####
            self.m1thread.setmode(self.mode)    # Update the mode after selection
            try:
                self.EMGthread.start()
            except:
                pass
            self.m1thread.start()
            if not self.plot:
                self.plot = True
            #### Change button, press the same button again can stop ####
            self.btn_connect.setDisabled(True)
            if self.mode == 0:
                self.cbChan.setDisabled(True)
            self.btn_start.setText("Stop")
            self.status = 2
            self.m1thread.startM1()  # Update status after selection

        elif self.status == 2:
            #### Change back to start status
            self.status = 1
            self.m1thread.stopM1()    # Change into recording mode
            self.plot = False
            self.btn_connect.setDisabled(True)
            self.cbChan.setDisabled(False)
            self.btn_start.setText("Start")

    def Exit(self):
        print("Exit run")
        self.close()

    ################################################################################
    #### Line2: Functions about saving ####
    ################################################################################

    def Saving(self):
        if self.Savingstatus == 1:
            self.cbChan.setDisabled(True)
            self.btn_Saving.setText("Stop Sampling!")
            self.Savingstatus = 2

            #### Start saving thread ####
            savingtime = 'Data\\Data' + time.strftime('_%m%d_%H%M%S') + '.csv'
            self.m1thread.All_queue.queue.clear()
            self.EMG_saving = DataSave(1, self.m1thread.All_queue, self.nch+1, savingtime)    # The number here (6, 15) is decided by the kinds of data you want to save
            self.EMG_saving.start()

        elif self.Savingstatus == 2:
            self.cbChan.setDisabled(True)
            self.Savingstatus = 1
            self.btn_Saving.setText("Start Sampling!")
            self.EMG_saving.terminate()
            print('Stop Saving!')

    #####################################
    #### Others: ComboBox ####
    #####################################

    def modechange(self, i):
        self.mode = i

        if i == 0:
            self.plot = False
        elif i == 1:
            self.plot = True

        print('Now in Mode %d' % i)
        self.init_dynamic_plot()

    def chanchange(self, i):
        self.Chanmode = i
        if i == 0:
            print("All EMG Mode")
        else:
            print(('EMG' + str(i) + ' Mode'))

    #########################
    #### Line0: Plotting ####
    #########################

    def init_dynamic_plot(self):
        self.graphWidget.setBackground('w')
        self.graphWidget.setYRange(0, self.nch*self.space, padding=0)
        self.graphWidget.setXRange(0, self.pd*self.fs, padding=0)
        arr = np.array([1 for k in np.arange(0, 1, 1/(self.pd*self.fs))])
        for x in range(0, self.nch):
            if x == 0:
                self.p = np.array(self.space*(self.nch-1)*arr)
            else:
                self.p = np.vstack((self.p, self.space*(self.nch-1-x)*arr))

        if self.plot_init == 0:
            # plot init run only once
            self.plot_init = 1
            self.real_line = [None] * self.nch  # [0] * self.nch

            chp = round((self.nch-1)/2)
            for x in range(0, self.nch):
                if x <= chp-1:
                    col = (0, 0, 255-x*25)
                elif x < self.nch-1:
                    col = (255-x*25, 0, 0)
                elif x == self.nch-1:
                    col = (0, 0, 0)

                pen = pg.mkPen(color=col, width=3)

                self.real_line[x] = self.graphWidget.plot(self.p[x], name=('EMG'+str(x+1)), pen=pen)
                self.real_line[x].setPos(0, 0)
        else:
            for x in range(0, self.nch):
                self.real_line[x].setData(self.p[x])
                self.real_line[x].setPos(0, 0)

    def update_plot(self, y):
        ######## This is how we update the plot. Mainly for testing not clinical using.                          ########
        ######## Change plotcounter to change the FPS, small number makes plotting smooth but may freeze easily. ########
        if self.plot:
            if self.plot_counter == round(self.fs/7.5):  # within loop self.fs/7.5, self.fs/100 outside
                if self.Chanmode == 0:
                    for x in range(0, self.nch):
                        self.real_line[x].setData(np.array(y[x][-self.pd*self.fs:])+self.space*(self.nch-1-x))
                else:
                    idx = self.Chanmode - 1
                    self.real_line[idx].setData(np.array(y[idx][-self.pd*self.fs:])+self.space*(self.nch-1-idx))

                if self.Chanmode == 0:
                    self.graphWidget.setYRange(0, self.nch*self.space, padding=0)
                else:
                    idx = self.Chanmode - 1
                    self.graphWidget.setYRange(self.space*(self.nch-2-idx), self.space*(self.nch-idx), padding=0)
                self.graphWidget.setXRange(0, self.pd*self.fs, padding=0)
                self.plot_counter = 0
            self.plot_counter = self.plot_counter+1
        else:
            self.plot_counter = 0
        return 1


def main():
    gl._init()
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()