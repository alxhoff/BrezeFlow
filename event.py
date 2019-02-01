from aenum import Enum

class eventType(Enum):
    SWITCH_OFF      = 0x1
    SWITCH_ON       = 0x10
    SCHED_SLICE     = 0x100
    FREQ_CHANGE     = 0x1000
    WAKEUP          = 0x10000
    IDLE            = 0x100000

class event:

    def __init__(self, PID, event):
        self.PID = PID
        self.event = event

class event_run_slice(event):

    def __init__(self, PID, start_time, cpu):
        event.__init__(self, PID, eventType.SWITCH_ON)
        self.start_time = start_time
        self.cpu = cpu

    def setFinishTime(self, finish_time):
        self.finish_time = finish_time
        self.duration = self.finish_time - self.start_time
        self.event |= SWITCH_ON

class event_freq_change(event):

    def __init__(self, PID, time, freq, load, cpu):
        event.__init__(self, PID, eventType.FREQ_CHANGE)
        self.freq = freq
        self.time = time
        self.load = load
        self.cpu = cpu

class event_wakeup(event):

    def __init__(self, PID, time, cpu):
        event.__init__(self, PID, eventType.WAKEUP)
        self.time = time

class event_idle(event):

    def __init__(self, time, cpu):
        event.__init__(self, 0, eventType.IDLE)
        self.time = time
        self.cpu = cpu

class process_exec:

    def __init__(self, PID):
        self.PID = PID
        self.run_slices = []

    def updateRunTime(self):
        self.run_time = 0
        for x, slice in enumerate(self.run_slices):
            self.run_time += slice.duration

    def getRunTime(self):
        return self.run_time

    def addRunSlice(self, run_slice):
        self.run_slices.append(run_slice)
        self.updateRunTime()



