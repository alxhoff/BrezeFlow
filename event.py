from aenum import Enum
import logging

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

class process_state(Enum):
    UNINTERRUPTIBLE_SLEEP_D = 0
    RUNNING_R = 1
    INTERRUPTIBLE_SLEEP_S = 2
    STOPPED_T = 3
    DEAD_X = 4
    ZOMBIE_Z = 5

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

class job_state(Enum):
    UNKNOWN = 0
    BINDER_WAKE = 1
    SCHED_WAKE = 2
    SCHED_SLEEP = 3
    BINDER_SLEEP = 4

"""
Each job represents a slice of thread execution. A job is comprised
of a sched switch event to wake and another to sleep it. A job will most commonly
be the execution of a task between uniterruptible sleep (D) states and running (R)
states.
"""

class job_node:

    def __init__(self, PID, state=job_state.BINDER_WAKE, initial=False,
            wake_event=None, sleep_event=None):
        self.PID = PID
        self.initial = initial
        self.state = state
        self.exec_time = 0
        self.wake_event = wake_event
        self.sleep_event = sleep_event

    def add_event_wake(self, wake_event):
        self.wake_event = wake_event

    def add_event_sleep(self, sleep_event):
        self.sleep_event = sleep_event

    def get_exec_time(self):
        if self.wake_event is not None and self.sleep_event is not None:
            if self.exec_time == 0:
                self.exec_time = sleep_event.time - wake_event.time
                return self.exec_time
            else:
                return self.exec_time
        else:
            return 0

"""
A task represents a collection of jobs that have been executed between a
wake event bringing the process out of sleep (S) until it returns to sleep from
the running state (R)

Because sched_switch events do not show the next state, the last event must be
kept so that when another switch event giving prev_state=S is performed the last
event is then known to be the sleep event and can then be processed accordingly.
As such task processing must have a lead of one job.
"""
class task_node:

    def __init__(self, binder_wake_event=None, initial=False,
            state=job_state.UNKNOWN):
        self.PID = binder_wake_event.to_proc
        self.jobs = []
        self.state = state

    def task_add_job(self, job_event):
        self.jobs.append(job_event)
        if self.state == job_state.BINDER_WAKE and isinstance(job_event,
                event_sched_switch):
            self.state == job_state.SCHED_WAKE

class process_branch:

    def __init__(self, PID, head=None):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Process branch created for: " + str(PID))

        self.PID = PID
        self.job_head = head
        self.task_head = head
        self.tasks = []
        if not head == None:
            self.tasks.append(head)

    def handle_event(self, job):
        # Wakeup events show us the same information as sched switch events and
        # as such can be neglected when it comes to generating directed graphs
        if isinstance(event, event_wakeup):
            return

        # Sched switch events are the key events to track task activity.
        # They show us which process was slept and which was woken. Showing the
        # previous task's state
        elif  isinstance(event, event_sched_switch):
            return

        # Freq change events give the time at which a frequency change occured.
        # Can be later used to calculate workload/energy consumption of threads
        # in relation to the system configuration as they were executed.
        elif isinstance(event, event_freq_change):
            return

        # Also used in the calculation of system load
        elif isinstance(event, event_idle):
            return

        # Binder transactions show IPCs between tasks. TODO
        elif isinstance(event, event_binder_call):
            return

        else:
            self.logger.debug("Unknown event")

        #check if branch has been started
        #if self.tasks == []:
            #create task
            #self.tasks.append(task_node(None, ))
