from aenum import Enum

class binder_type(Enum):
    UNKNOWN = 0
    CALL = 1
    REPLY = 2
    ASYNC = 3

class event_type_chars(Enum):
    SCHED_SWITCH = 'S'
    FREQ_CHANGE = 'F'
    WAKEUP = 'W'
    IDLE = 'I'
    BINDER = 'B'

class event:

    def __init__(self, PID, time, cpu):
        self.PID = PID
        self.time = time
        self.cpu = cpu

class event_sched_switch(event):

    def __init__(self, PID, time, cpu, prev_state, next_pid):
        event.__init__(self, PID, time, cpu)
        self.prev_state = prev_state
        self.next_pid = next_pid

class event_freq_change(event):

    def __init__(self, PID, time, cpu, freq, load):
        event.__init__(self, PID, time, cpu)
        self.freq = freq
        self.load = load

class event_wakeup(event):

    def __init__(self, PID, time, cpu):
        event.__init__(self, PID, time, cpu)

class event_idle(event):

    def __init__(self, time, cpu, state):
        event.__init__(self, 0, time, cpu)
        self.state = state

class event_binder_call(event):

    def __init__(self, PID, time, trans_type, to_proc, trans_ID, flags, code):
        event.__init__(self, PID, time, 99)
        if trans_type == 0:
            if flags & 0b1:
                self.trans_type = binder_type.ASYNC
            else:
                self.trans_type = binder_type.CALL
        elif trans_type == 1:
            self.trans_type = binder_type.REPLY
        else:
            self.trans_type = binder_type.UNKNOWN
        self.to_proc = to_proc
        self.trans_ID = trans_ID
        self.flags = flags
        self.code = code

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
