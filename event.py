from aenum import Enum
import logging

class binderType(Enum):
    UNKNOWN = 0
    CALL = 1
    REPLY = 2
    ASYNC = 3

class jobType(Enum):
    SCHED_SWITCH = 'S'
    FREQ_CHANGE = 'F'
    WAKEUP = 'W'
    IDLE = 'I'
    BINDER_SEND = 'B'
    BINDER_RECV = 'R'

class threadState(Enum):
    UNINTERRUPTIBLE_SLEEP_D = 'D'
    RUNNING_R = 'R'
    INTERRUPTIBLE_SLEEP_S = 'S'
    STOPPED_T = 'T'
    DEAD_X = 'X'
    ZOMBIE_Z = 'Z'

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
                self.trans_type = binderType.ASYNC
            else:
                self.trans_type = binderType.CALL
        elif trans_type == 1:
            self.trans_type = binderType.REPLY
        else:
            self.trans_type = binderType.UNKNOWN
        self.to_proc = to_proc
        self.trans_ID = trans_ID
        self.flags = flags
        self.code = code
        self.recv_time = 0

class job_state(Enum):
    UNKNOWN = 0
    BINDER_WAKE = 1
    SCHED_SWITCH = 2
    BINDER_SLEEP = 3

"""
Each job represents a slice of thread execution. A job is comprised
of a sched switch event to wake and another to sleep it. A job will most commonly
be the execution of a task between uniterruptible sleep (D) states and running (R)
states.
"""

class job_node:

    def __init__(self, PID, state=job_state.BINDER_WAKE, wake_event=None,
            sleep_event=None):
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

class taskState(Enum):
    UNKNOWN = 0
    EXECUTING = 1
    BLOCKED = 2
    FINISHED = 3

"""
A task represents a collection of jobs that have been executed between a
wake event bringing the process out of sleep (S) until it returns to sleep from
the running state (R)

Because sched_switch events do not show the next state, the last event must be
kept so that when another switch event giving prev_state=S is performed the last
event is then known to be the sleep event and can then be processed accordingly.
As such task processing must have a lead of one job.
"""
class taskNode:

    def __init__(self, taskState=taskState.EXECUTING):
        self.jobs = []
        self.state = taskState

    # At the task level a job changes the state of the task
    # Switch event with prev state R puts the task into a blocked state.
    # A switch event with a prev state of D puts the task into a running state.
    # TODO binder transactions will be processed to form dependency connections
    def add_job(self, event, jobType):
        self.jobs.append(event)
        #handle event a
        if jobType == jobType.SCHED_SWITCH:
            #thread sleep
            if event.prev_state == threadState.RUNNING_R.value:
                self.state = taskState.BLOCKED
            #thread wakeup
            elif event.prev_state == threadState.UNINTERRUPTIBLE_SLEEP_D.value:
                self.state = taskState.FINISHED

    def finished(self):
        self.state = taskState.FINISHED

class processBranch:
    """
    Events must be added to the "branch" of their PID. The data is processed
    such that each PID runs down a single file branch that is then branched out
    of and into to represent IPCs. The tree consists of tasks, each task being
    comprised of jobs/slices (time spend executing thread between a wake and
    sleep event).
    """

    def __init__(self, PID, head=None):
        self.PID = PID
        self.tasks = []
        if not head == None:
            self.tasks.append(head)

    # At the process branch level the only significant difference is that a job
    # can signify the end of the current task by being a sched switch event with
    # prev_state = S
    def add_job(self, event, event_type=job_state.UNKNOWN):
        #first job/task
        if self.tasks == []: #TODO check if first event is task sleeping
            self.tasks.append(taskNode(event_type))

        #if the state marks the last sched switch event as a sleep event
        if event_type == job_state.SCHED_SWITCH and \
                event.prev_state == threadState.INTERRUPTIBLE_SLEEP_S :
            #wrap up current task
            self.tasks[-1].finished
            #create new task
            self.tasks.append(taskNode(taskState.EXECUTING))
            #return
            return

        #all other job types
        self.tasks[-1].add_job(event, event_type)

# Binder transactions are sometimes directed to the parent binder thread of a
# system service. The exact PID of the child thread is not known when the
# transaction is done. A list of open transaction is to be maintained where each
# entry shows possible child thread PID that could appear in the corresponding
# wake event. Allowing binder transactions to be matched to their corresponding
# wake event.
class pendingBinderTransaction:

    def __init__(self, event, PIDt):
        self.child_PIDs = PIDt.findChildBinderThreads(event.to_proc)
        self.event = event

class processTree:

    process_branches = []
    pending_binder_transactions = []

    def __init__(self, PIDt):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Process tree created")

        self.PIDt = PIDt

        for pid in self.PIDt.allPIDStrings:
            self.process_branches.append(processBranch(int(pid), None))

    def handle_event(self, event):
        print event.PID
        print event
        # Wakeup events show us the same information as sched switch events and
        # as such can be neglected when it comes to generating directed graphs
        if isinstance(event, event_wakeup):
            return

        # Sched switch events are the key events to track task activity.
        # They show us which process was slept and which was woken. Showing the
        # previous task's state
        elif  isinstance(event, event_sched_switch):
            process_branch = \
                    self.process_branches[self.PIDt.getPIDStringIndex(event.PID)]
            process_branch.add_job(event, event_type=job_state.SCHED_SWITCH)
            self.logger.debug("Sched switch event added as job")
            return

        # Freq change events give the time at which a frequency change occured.
        # Can be later used to calculate workload/energy consumption of threads
        # in relation to the system configuration as they were executed.
        elif isinstance(event, event_freq_change):
            return

        # Also used in the calculation of system load
        elif isinstance(event, event_idle):
            return

        # Binder transactions show IPCs between tasks.
        # As a binder transaction represents the blocking of the client task
        # the transactions are processed as sleep events for the client tasks.
        # Binder transactions happen in two parts, they send to a binder thread
        # then the tread sends to the target task. As such binder transactions
        # are identified by if they send or recv from a binder thread then
        # handled accordingly
        elif isinstance(event, event_binder_call):
            process_branch = \
                    self.process_branches[self.PIDt.getPIDStringIndex(event.PID)]
            # Sending to binder thread
            if str(event.PID) in self.PIDt.allAppPIDStrings:
                # Push binder event on to pending list so that when the second
                # half of the transaction is performed the events can be merged.
                # The first half should give the event PID and time stamp
                # The second half gives to_proc PID and recv_time timestamp
                self.pending_binder_transactions.append(\
                    pendingBinderTransaction(event,self.PIDt))
                # create binder send job in client thread tree (current tree)
                process_branch.add_job(event, event_type=jobType.BINDER_SEND)
                self.logger.debug("Binder event from: " + str(event.PID) + \
                        " to " + str(event.to_proc))
                print "Binder event from: " + str(event.PID) + \
                        " to " + str(event.to_proc)

            # From binder thread to target proc
            elif str(event.PID) in self.PIDt.allBinderPIDStrings:
                print "Binder transaction from binder thread " + str(event.PID)
                # get event from binder transactions list and merge
                if self.pending_binder_transactions != []:
                    print "pending transactions"
                    for x, transaction in enumerate(self.pending_binder_transactions):
                        # If the binder thread that is completing the transaction
                        # is a child of a previous transactions parent binder PID
                        if any(pid == event.PID for pid in transaction.child_PIDs):
                            #TODO handle binder transaction (edge creation)
                            # merge
                            print "Updated to_proc " + str(transaction.event.to_proc)\
                                    + " to " + str(event.to_proc)
                            transaction.event.to_proc = event.to_proc
                            transaction.event.recv_time = event.time
                        # Add job to the branch of the child PID (this branch)
                        process_branch.add_job(transaction.event, \
                                     event_type=job_state.BINDER_WAKE)
                        del self.pending_binder_transactions[x]
                        break
            else:
                print "Unhandled binder"

            return

        else:
            self.logger.debug("Unknown event")

