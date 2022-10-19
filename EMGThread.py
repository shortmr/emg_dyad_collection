######################################################
## EMG thread to send the EMG to the main thread    ##
######################################################

from PyQt5.QtCore import QThread, pyqtSignal
from queue import Queue

from EMG_receive import EMG_collector


class EMGThread(QThread):
    signal = pyqtSignal('PyQt_PyObject')

    def __init__(self,out_q, out_EMG, fs, nch):
        QThread.__init__(self)
        print('initialize EMG Sensor')
        self.EMG_queue = Queue()
        self.EMG_ch = [0] * nch

        self.emg = EMG_collector(fs, nch)
        self.emg.initialize()
        self.timenow = 0
        self.EMGcounter = 0
        self.Out = out_q
        self.OutEMG = out_EMG
        self.fs = fs
        self.nch = nch

    def run(self):
        while True:
            self.EMG_ch = self.emg.collect_EMG()
            self.EMGcounter = self.EMGcounter + 1

            ######## Data Communication with main file, using Queue ########
            for x in range(0, self.nch):
                self.OutEMG.put(self.EMG_ch[x])

            self.Out.put(self.EMGcounter)

            ######## Use this counter to sychronize the EMG with M1 device ########
            if self.EMGcounter >= round(self.fs/100):
                self.EMGcounter = 0

        print("Exit run")
