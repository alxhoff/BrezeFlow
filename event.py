from aenum import Enum

class eventType(Enum):
    SCHED_OFF   = 0x1
    SCHED_ON    = 0x10
    SCHED_SLICE = 0x100
    FREQ_CHANGE = 0x1000

class event:

    def __init__(self, PID, event):
        self.PID = PID
        self.event = event

class event_run_slice(event):

    def __init__(self, PID, start_time):
        event.__init__(self, PID, eventType.SCHED_ON)
        self.start_time = start_time

    def setFinishTime(self, finish_time):
        self.finish_time = finish_time
        self.duration = self.finish_time - self.start_time
        self.event |= SCHED_ON

class event_freq_change(event):

    def __init__(self, PID, time, freq):
        event.__init__(self, PID, eventType.FREQ_CHANGE)
        self.freq = freq

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



