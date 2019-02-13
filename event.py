from __builtin__ import type

from aenum import Enum
import logging
import networkx as nx


class BinderType(Enum):
    UNKNOWN = 0
    CALL = 1
    REPLY = 2
    ASYNC = 3


class JobType(Enum):
    UNKNOWN = 'U'
    SCHED_SWITCH_IN = 'S'
    SCHED_SWITCH_OUT = 'O'
    FREQ_CHANGE = 'F'
    WAKEUP = 'W'
    IDLE = 'I'
    BINDER_SEND = 'B'
    BINDER_RECV = 'R'


class ThreadState(Enum):
    UNINTERRUPTIBLE_SLEEP_D = 'D'
    RUNNING_R = 'R'
    INTERRUPTIBLE_SLEEP_S = 'S'
    STOPPED_T = 'T'
    DEAD_X = 'X'
    ZOMBIE_Z = 'Z'


class Event:

    def __init__(self, PID, time, cpu):
        self.PID = PID
        self.time = time
        self.cpu = cpu


class EventSchedSwitch(Event):

    def __init__(self, PID, time, cpu, prev_state, next_pid):
        Event.__init__(self, PID, time, cpu)
        self.prev_state = prev_state
        self.next_pid = next_pid


class EventFreqChange(Event):

    def __init__(self, PID, time, cpu, freq, load):
        Event.__init__(self, PID, time, cpu)
        self.freq = freq
        self.load = load


class EventWakeup(Event):

    def __init__(self, PID, time, cpu):
        Event.__init__(self, PID, time, cpu)


class EventIdle(Event):

    def __init__(self, time, cpu, state):
        Event.__init__(self, 0, time, cpu)
        self.state = state


class EventBinderCall(Event):

    def __init__(self, PID, time, trans_type, dest_proc, trans_ID, flags, code):
        Event.__init__(self, PID, time, 99)
        if trans_type == 0:
            if flags & 0b1:
                self.trans_type = BinderType.ASYNC
            else:
                self.trans_type = BinderType.CALL
        elif trans_type == 1:
            self.trans_type = BinderType.REPLY
        else:
            self.trans_type = BinderType.UNKNOWN
        self.dest_proc = dest_proc
        self.trans_ID = trans_ID
        self.flags = flags
        self.code = code
        self.recv_time = 0


class TaskState(Enum):
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


class TaskNode:

    def __init__(self):
        self.events = []
        self.start_time = 0
        self.finish_time = 0
        self.exec_time = 0
        self.graph = nx.DiGraph()
        self.state = TaskState.EXECUTING

    def add_job(self, event):

        #save event to parent task
        self.events.append(event)

        # add event node to task subgraph
        self.graph.add_node(event)

        # create graph edge if not the first job
        if len(self.events) > 1:
            self.graph.add_edge(self.events[-2], self.events[-1])

    def finished(self):
        self.state = TaskState.FINISHED
        self.start_time = self.events[0].time
        self.finish_time = self.events[-1].time
        self.exec_time = self.finish_time - self.start_time


class ProcessBranch:

    """
    Events must be added to the "branch" of their PID. The data is processed
    such that each PID runs down a single file branch that is then branched out
    of and into to represent IPCs. The tree consists of tasks, each task being
    comprised of jobs/slices (time spend executing thread between a wake and
    sleep event).
    """

    def __init__(self, pid, start, graph):
        self.PID = pid
        self.tasks = []
        self.start = start
        self.active = False
        self.graph = graph

    # At the process branch level the only significant difference is that a job
    # can signify the end of the current task by being a sched switch event with
    # prev_state = S
    def add_job(self, event, event_type=JobType.UNKNOWN):
        # first job/task for PID branch
        if not self.tasks:

            self.tasks.append(TaskNode())
            self.tasks[-1].add_job(event)

            # task could be finishing
            if event_type == JobType.SCHED_SWITCH_OUT and \
                    event.prev_state == ThreadState.INTERRUPTIBLE_SLEEP_S.value:
                    self.active = False
                    self.tasks[-1].finished()
                    self.graph.add_node(self.tasks[-1], event=event, type=JobType.SCHED_SWITCH_OUT)
                    return

            self.graph.add_node(self.tasks[-1], event=event, type=JobType.SCHED_SWITCH_IN)
            self.active = True

            return

        # If a task is being switched into from sleeping
        # New task STARTING
        if event_type == JobType.SCHED_SWITCH_IN and self.active == False:

            # create new task
            self.tasks.append(TaskNode())
            # add current event
            self.tasks[-1].add_job(event)
            # create entry node for task
            self.graph.add_node(self.tasks[-1], event=event, type=JobType.SCHED_SWITCH_IN)

            # set task to running
            self.active = True

            # there should always be at least 2 tasks if this is called
            # connect two sequential tasks with an edge
            if len(self.tasks) >= 2:
                self.graph.add_edge(self.tasks[-2], self.tasks[-1])

            return

        # If the state marks the last sched switch event as a sleep event
        # Current task FINISHING
        elif event_type == JobType.SCHED_SWITCH_OUT and \
                event.prev_state == ThreadState.INTERRUPTIBLE_SLEEP_S.value:

            # wrap up current task
            self.tasks[-1].add_job(event)
            self.tasks[-1].finished()
            self.active = False

            # add task node to graph
            self.graph.add_node(self.tasks[-1], event=event, type=JobType.SCHED_SWITCH_OUT)

            # link task node to beginning of sub-graph
            self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[0])
            # link the end of the subgraph to the task node
            self.graph.add_edge(self.tasks[-1].events[-1], self.tasks[-1])
            # add connecting nodes in task
            self.graph.add_edges_from(self.tasks[-1].graph.edges)

            return

        # all other job types just need to get added to the task
        self.tasks[-1].add_job(event)

# Binder transactions are sometimes directed to the parent binder thread of a
# system service. The exact PID of the child thread is not known when the
# transaction is done. A list of open transaction is to be maintained where each
# entry shows possible child thread PID that could appear in the corresponding
# wake event. Allowing binder transactions to be matched to their corresponding
# wake event.


class PendingBinderTransaction:

    def __init__(self, event, PIDt):
        self.parent_PID = event.dest_proc
        self.child_PIDs = PIDt.findChildBinderThreads(event.dest_proc)
        self.event = event


class ProcessTree:

    def __init__(self, PIDt):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Process tree created")
        self.process_branches = []
        self.pending_binder_transactions = []
        self.PIDt = PIDt
        self.index = 0
        self.graph = nx.DiGraph()

        for pid in self.PIDt.allPIDStrings:
            self.process_branches.append(ProcessBranch(int(pid), None, self.graph))

    def getIndex(self):
        self.index += 1
        return self.index - 1

    def handle_event(self, event):
        # Wakeup events show us the same information as sched switch events and
        # as such can be neglected when it comes to generating directed graphs
        if isinstance(event, EventWakeup):
            return

        # Sched switch events are the key events to track task activity.
        # They show us which process was slept and which was woken. Showing the
        # previous task's state
        elif isinstance(event, EventSchedSwitch):
            # task being switched out
            # if task of interest
            index = self.PIDt.getPIDStringIndex(event.PID)
            if index is not None and index != 0:
                process_branch = self.process_branches[index]
                process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_OUT)
                self.logger.debug("Sched switch in event added as job")
            # task being switched in
            index = self.PIDt.getPIDStringIndex(event.next_pid)
            if index is not None and index != 0:
                process_branch = self.process_branches[index]
                process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_IN)
            return

        # Freq change events give the time at which a frequency change occured.
        # Can be later used to calculate workload/energy consumption of threads
        # in relation to the system configuration as they were executed.
        elif isinstance(event, EventFreqChange):
            return

        # Also used in the calculation of system load
        elif isinstance(event, EventIdle):
            return

        # Binder transactions show IPCs between tasks.
        # As a binder transaction represents the blocking of the client task
        # the transactions are processed as sleep events for the client tasks.
        # Binder transactions happen in two parts, they send to a binder thread
        # then the tread sends to the target task. As such binder transactions
        # are identified by if they send or recv from a binder thread then
        # handled accordingly
        elif isinstance(event, EventBinderCall):

            # FROM CLIENT PROC TO BINDER THREAD
            if str(event.PID) in self.PIDt.allPIDStrings:
                process_branch = \
                    self.process_branches[self.PIDt.getPIDStringIndex(event.PID)]

                # Push binder event on to pending list so that when the second
                # half of the transaction is performed the events can be merged.
                # The first half should give the event PID and time stamp
                # The second half gives to_proc PID and recv_time timestamp
                self.pending_binder_transactions.append(\
                    PendingBinderTransaction(event, self.PIDt))

                # create binder send job in client thread tree (current tree)
                #process_branch.add_job(event, event_type=JobType.BINDER_SEND)

                self.logger.debug("Binder event from: " + str(event.PID) + \
                        " to " + str(event.dest_proc))

            # FROM BINDER THREAD TO SERVER PROC
            elif str(event.PID) in self.PIDt.allBinderPIDStrings:
                process_branch = \
                    self.process_branches[self.PIDt.getPIDStringIndex(event.dest_proc)]

                # get event from binder transactions list and merge
                if self.pending_binder_transactions:
                    for x, transaction in \
                            enumerate(self.pending_binder_transactions):

                        # If the binder thread that is completing the transaction
                        # is a child of a previous transactions parent binder PID
                        if any(pid == event.PID for pid in transaction.child_PIDs) or \
                                event.PID == transaction.parent_PID:

                            # merge
                            transaction.event.dest_proc = event.dest_proc
                            transaction.event.recv_time = event.time

                        # Add job to the branch of the child PID (this branch)
                        # process_branch.add_job(transaction.event, event_type=JobType.BINDER_RECV)

                        # Binder edge transaction creation
                        self.graph.add_edge(
                            # original process branch from transaction PID
                            self.process_branches[\
                                self.PIDt.getPIDStringIndex(transaction.event.PID)].tasks[-1],
                            # target process branch from current event
                            self.process_branches[\
                                self.PIDt.getPIDStringIndex(transaction.event.dest_proc)].tasks[-1])

                        # remove completed transaction
                        del self.pending_binder_transactions[x]
                        return
            else:
                print "Unhandled binder"

            return

        else:
            self.logger.debug("Unknown event")

