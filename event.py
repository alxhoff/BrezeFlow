import logging

import networkx as nx
from aenum import Enum
from pydispatch import dispatcher
from pid import PID
from adbinterface import *
import re
from metrics import SystemMetrics

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
    ZOMBIE_Z = 'Z'


class Event:

    def __init__(self, PID, time, cpu, name):
        self.PID = PID
        self.time = time
        self.cpu = cpu
        self.name = name


class EventSchedSwitch(Event):

    def __init__(self, PID, time, cpu, name, prev_state, next_pid):
        Event.__init__(self, PID, time, cpu, name)
        self.prev_state = prev_state
        self.next_pid = next_pid


class EventFreqChange(Event):

    def __init__(self, PID, time, cpu, freq, load, target_cpu):
        Event.__init__(self, PID, time, cpu, "freq change")
        self.freq = freq
        self.load = load
        self.target_cpu = target_cpu


class EventWakeup(Event):

    def __init__(self, PID, time, cpu, name):
        Event.__init__(self, PID, time, cpu, name)


class EventIdle(Event):

    def __init__(self, time, cpu, name, state):
        Event.__init__(self, 0, time, cpu, name)
        self.state = state


class EventBinderCall(Event):

    def __init__(self, PID, time, cpu, name, trans_type, dest_proc, flags, code):
        Event.__init__(self, PID, time, cpu, name)
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
        self.flags = flags
        self.code = code
        self.recv_time = 0

class EventMaliUtil(Event):

    def __init__(self, PID, time, cpu, util, freq):
        Event.__init__(self, PID, time, cpu, "mali util")
        self.util = util
        self.freq = freq


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

    """ Calculating task cycles works on incremental summing. If the CPU on which the process is
    running changes or the frequency changes then the cycles variable is updated and the calc time
    shifted to the point of the event. As such the calc time stores the time since the exec time
    was last changed, and given that the CPU and frequency have been fixed during that time,
    the cycles is easily updated using a += and the current values (before updating them)
    """
    def __init__(self, graph):
        self.events = []
        self.cycles = 0
        self.start_time = 0
        self.calc_time = 0
        self.finish_time = 0
        self.exec_time = 0
        self.graph = graph
        self.state = TaskState.EXECUTING

    def add_job(self, event):

        # If first job
        if not self.events:
            self.start_time = event.time
            self.calc_time = event.time

        # save event to parent task
        self.events.append(event)

        # add event node to task sub-graph
        if isinstance(event, EventSchedSwitch):
            self.graph.add_node(event, label=str(event.time)[:-6] + "." + str(event.time)[-6:] +
                                             " CPU: " + str(event.cpu) + "\n" + str(event.PID)
                                             + " ==> " + str(event.next_pid)
                                             + "\nPrev state: " + str(event.prev_state)
                                             + "\n" + str(event.name) + "\n"
                                             + str(event.__class__.__name__)
                                , fillcolor='bisque1', style='filled', shape='box')
        elif isinstance(event, EventBinderCall):
            self.graph.add_node(event, label=str(event.time)[:-6] + "." + str(event.time)[-6:] +
                                             " CPU: " + str(event.cpu) + "\n" + str(event.PID)
                                             + " ==> " + str(event.dest_proc)
                                             + "\n" + str(event.name)
                                             + "\n" + str(event.__class__.__name__)
                                , fillcolor='aquamarine1', style='filled', shape='box')

        # create graph edge if not the first job
        if len(self.events) >= 2:
            self.graph.add_edge(self.events[-2], self.events[-1], color='violet', dir='forward')

    def update_cycles(self, prev_freq, time):
        self.cycles += (time - self.calc_time) * prev_freq / 3
        self.calc_time = time

    def finished(self, cur_freq):
        self.state = TaskState.FINISHED
        self.finish_time = self.events[-1].time
        self.exec_time = self.finish_time - self.start_time
        self.cycles += (self.finish_time - self.calc_time) * cur_freq / 3


"""
A binder node represents a transaction between two thread. They contain only one
job, the job that the thread issues to the target process
"""


class BinderNode(TaskNode):

    def __init__(self, graph):
        TaskNode.__init__(self, graph)


class CPUBranch:

    def __init__(self, cpu_number, initial_freq, initial_load, graph):
        self.cpu_num = cpu_number
        self.freq = initial_freq
        self.prev_freq = initial_freq
        self.load = initial_load
        self.prev_load = initial_load
        self.events = []
        self.graph = graph
        self.signal_util = "util_change" + str(self.cpu_num)
        self.signal_freq = "freq_change" + str(self.cpu_num)

    def send_freq_change_event(self):
        dispatcher.send(signal=self.signal_freq, sender=dispatcher.Any)

    def send_load_change_event(self):
        dispatcher.send(signal=self.signal_util, sender=dispatcher.Any)

    def add_job(self, event):
        # create new event
        self.events.append(event)

        # Update current frequency
        if event.freq != self.freq:
            self.prev_freq = self.freq
            self.freq = event.freq
            # Inform PID branches that are running on this CPU that a freq change event occurred
            self.send_freq_change_event()

        if event.load != self.load:
            self.prev_load = self.load
            self.load = event.load
            self.send_load_change_event()

        self.graph.add_node(self.events[-1],
                            label=str(self.events[-1].time)[:-6] + "." + str(self.events[-1].time)[-6:]
                                  + "\nCPU: " + str(event.cpu) + " Load: " + str(event.load)
                                  + "\nFreq: " + str(event.freq)
                                  + "\n" + str(event.__class__.__name__), style='filled', shape='box')

        # These edges simply follow a PID, do not show any IPCs or IPDs
        if len(self.events) >= 2:
            self.graph.add_edge(self.events[-2], self.events[-1], style='bold')


class GPUBranch:

    def __init__(self, initial_freq, initial_util, graph):
        self.freq = initial_freq
        self.prev_freq = initial_freq
        self.util = initial_util
        self.prev_util = initial_util
        self.graph = graph
        self.events = []
        self.signal_util = "gpu_util_change"
        self.signal_freq = "gpu_freq_change"

    def send_util_change_event(self):
        dispatcher.send(signal=self.signal_util, sender=dispatcher.Any)

    def send_freq_change_event(self):
        dispatcher.send(signal=self.signal_freq, sender=dispatcher.Any)

    def add_job(self, event):

        self.events.append(event)

        if event.util != self.util:
            self.prev_util = self.util
            self.util = event.util
            self.send_util_change_event()

        if event.freq != self.freq:
            self.prev_freq = self.freq
            self.freq = event.freq
            self.send_freq_change_event()

        self.graph.add_node(self.events[-1],
                            label=str(self.events[-1].time)[:-6] + "." + str(self.events[-1].time)[-6:]
                                    + "\nUtil: " + str(self.events[-1].util)
                                    + "\nFreq: " + str(self.events[-1].freq)
                                    + "\n" + str(self.events[-1].__class__.__name__), style='filled',
                                    shape='box', fillcolor='magenta')

class ProcessBranch:
    """
    Events must be added to the "branch" of their PID. The data is processed
    such that each PID runs down a single file branch that is then branched out
    of and into to represent IPCs. The tree consists of tasks, each task being
    comprised of jobs/slices (time spend executing thread between a wake and
    sleep event).
    """

    def __init__(self, pid, start, graph, PIDt, cpus, gpu):
        self.PID = pid
        self.tasks = []
        self.start = start
        self.active = False
        self.graph = graph
        self.PIDt = PIDt
        self.CPU = None
        self.CPUs = cpus
        self.gpu = gpu

    def connect_to_cpu_event(self, cpu):
        dispatcher.connect(self.handle_cpu_freq_change, signal=self.CPUs[cpu].signal_freq,
                            sender=dispatcher.Any)
        dispatcher.connect(self.handle_cpu_util_change, signal=self.CPUs[cpu].signal_util,
                            sender=dispatcher.Any)

    def disconnect_from_cpu_event(self, cpu):
        dispatcher.disconnect(self.handle_cpu_freq_change, signal=self.CPUs[cpu].signal_freq,
                            sender=dispatcher.Any)
        dispatcher.disconnect(self.handle_cpu_util_change, signal=self.CPUs[cpu].signal_util,
                            sender=dispatcher.Any)

    def connect_to_gpu_events(self):
        dispatcher.connect(self.handle_gpu_freq_change, signal=self.gpu.signal_freq,
                            sender=dispatcher.Any)
        dispatcher.connect(self.handle_gpu_util_change, signal=self.gpu.signal_util,
                            sender=dispatcher.Any)

    def get_cur_cpu_freq(self):
        return self.CPUs[self.CPU].freq

    def get_cur_cpu_prev_freq(self):
        return self.CPUs[self.CPU].prev_freq

    def get_cur_cpu_last_freq_switch(self):
        if self.CPUs[self.CPU].events:
            return self.CPUs[self.CPU].events[-1].time
        else:
            return None

    def handle_cpu_freq_change(self):
        if self.tasks:
            self.tasks[-1].update_cycles(self.get_cur_cpu_prev_freq(),
                                         self.get_cur_cpu_last_freq_switch())

    def handle_cpu_util_change(self):
        #TODO
        return

    def handle_cpu_num_change(self, time):
        if self.tasks:
            self.tasks[-1].update_cycles(self.get_cur_cpu_freq(), time)

    def handle_gpu_freq_change(self):
        #TODO
        return

    def handle_gru_util_change(self):
        #TODO
        return

    # At the process branch level the only significant difference is that a job
    # can signify the end of the current task by being a sched switch event with
    # prev_state = S
    def add_job(self, event, event_type=JobType.UNKNOWN):

        # CPU association
        if self.CPU is None:
            self.CPU = event.cpu
            self.connect_to_cpu_event(self.CPU)

        # first job/task for PID branch
        if not self.tasks:

            self.tasks.append(TaskNode(self.graph))
            self.tasks[-1].add_job(event)

            # task could be finishing
            if event_type == JobType.SCHED_SWITCH_OUT and \
                    event.prev_state == ThreadState.INTERRUPTIBLE_SLEEP_S.value:
                self.active = False
                self.tasks[-1].finished(self.get_cur_cpu_freq())

                #TODO ADD NODE HERE
                return

            self.active = True

            return

        if event_type == JobType.SCHED_SWITCH_IN:
            # If the CPU has changed
            if event.cpu != self.CPU:
                # Update current task's cycle count in case new CPU has different speed
                self.handle_cpu_num_change(event.time)

                # Change event signal for freq change
                self.disconnect_from_cpu_event(self.CPU)
                self.CPU = event.cpu
                self.connect_to_cpu_event(self.CPU)


        # If a task is being switched into from sleeping
        # New task STARTING
        if event_type == JobType.SCHED_SWITCH_IN and self.active is False:

            # create new task
            self.tasks.append(TaskNode(self.graph))
            # add current event
            self.tasks[-1].add_job(event)

            # set task to running
            self.active = True

            # These edges simply follow a PID, do not show any IPCs or IPDs
            if len(self.tasks) >= 2:
                self.graph.add_edge(self.tasks[-2], self.tasks[-1], color='lightseagreen', style='dashed')

            return

        # If the state marks the last sched switch event as a sleep event
        # Current task FINISHING
        elif event_type == JobType.SCHED_SWITCH_OUT and \
                event.prev_state == ThreadState.INTERRUPTIBLE_SLEEP_S.value and \
                str(event.PID) not in self.PIDt.allBinderPIDStrings:

            # wrap up current task
            self.tasks[-1].add_job(event)
            self.tasks[-1].finished(self.get_cur_cpu_freq())
            self.active = False

            self.graph.add_node(self.tasks[-1],
                                label=str(self.tasks[-1].start_time)[:-6] + "."
                                    + str(self.tasks[-1].start_time)[-6:]
                                    + " ==> " + str(self.tasks[-1].finish_time)[:-6] + "."
                                    + str(self.tasks[-1].finish_time)[-6:]
                                    + " CPU: " + str(event.cpu) + "\npid: " + str(event.PID)
                                    + "\nGPU: " + str(SystemMetrics.current_metrics.gpu_freq) + " "
                                    + str(SystemMetrics.current_metrics.gpu_util)
                                    + "\n" + str(event.name)
                                    + "\nDuration: " + str(self.tasks[-1].exec_time)
                                    + "\nCycles: " + str(self.tasks[-1].cycles)
                                    + "\n" + str(self.tasks[-1].__class__.__name__), fillcolor='darkolivegreen3',
                                style='filled,bold,rounded', shape='box')

            # link task node to beginning of sub-graph
            self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[0], color='blue',
                                dir='forward')
            # link the end of the subgraph to the task node
            self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[-1], color='red',
                                dir='back')
            return

        # binder events always single tasks, therefore adding them
        # must create and finish a task
        elif event_type == JobType.BINDER_RECV:
            self.tasks.append(BinderNode(self.graph))
            self.tasks[-1].add_job(event)
            self.tasks[-1].finished(self.get_cur_cpu_freq())
            # create binder task node
            self.graph.add_node(self.tasks[-1],
                                label=str(self.tasks[-1].start_time)[:-6]
                                      + "." + str(self.tasks[-1].start_time)[-6:] + "\npid: "
                                      + str(event.PID)
                                      + "  dest PID: " + str(event.dest_proc)
                                      + "\n" + str(event.name)
                                      + "\n" + str(self.tasks[-1].__class__.__name__),
                                fillcolor='coral', style='filled,bold', shape='box')
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
        self.send_event = event


class PendingBinderTask:

    def __init__(self, from_event, dest_event):
        self.from_pid = from_event.PID
        self.dest_pid = dest_event.dest_proc
        self.binder_thread = dest_event.PID
        self.time = from_event.time
        self.duration = dest_event.time - from_event.time


class ProcessTree:

    def __init__(self, PIDt, metrics):
        logging.basicConfig(filename="pytracer.log",
                            format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Process tree created")

        self.metrics = metrics
        self.graph = nx.DiGraph()
        self.PIDt = PIDt

        self.cpus = []
        self.process_branches = []
        self.pending_binder_transactions = []
        self.pending_binder_tasks = []

        self.gpu = GPUBranch(self.metrics.gpu_freq, self.metrics.gpu_util, self.graph)

        for pid in self.PIDt.allPIDStrings:
            self.process_branches.append(ProcessBranch(int(pid), None, self.graph,
                                                       self.PIDt, self.cpus, self.gpu))

        for x in range(0, self.metrics.core_count):
            self.cpus.append(CPUBranch(x, self.metrics.core_freqs[x],
                                       self.metrics.core_loads[x], self.graph))

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

                # if switched in because of binder
                for x, task in \
                        enumerate(self.pending_binder_tasks):
                    if event.next_pid == task.dest_pid:
                        # Binder edge transaction creation between
                        # sending proc: transaction.event.PID
                        # and target proc: event.dest_proc
                        # problem is target task doesn't exist yet and the transaction
                        # must be put off as pending until it is created

                        # TODO here add binder event to binder branch
                        binder_branch = self.process_branches[ \
                            self.PIDt.getPIDStringIndex(task.binder_thread)]

                        # edge from prev task to binder thread
                        self.graph.add_edge(
                            # original process branch that started transaction
                            self.process_branches[ \
                                self.PIDt.getPIDStringIndex(task.from_pid)].tasks[-1],
                            # this branch as it is being woken
                            self.process_branches[ \
                                self.PIDt.getPIDStringIndex(task.binder_thread)].tasks[-1],
                            color='palevioletred3', dir='forward', style='bold')

                        #
                        process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_IN)

                        # edge from binder thread to next task
                        self.graph.add_edge(
                            # original process branch that started transaction
                            self.process_branches[ \
                                self.PIDt.getPIDStringIndex(task.binder_thread)].tasks[-1],
                            # this branch as it is being woken
                            self.process_branches[ \
                                self.PIDt.getPIDStringIndex(task.dest_pid)].tasks[-1],
                            color='yellow3', dir='forward')

                        # remove binder task that is now complete
                        del self.pending_binder_tasks[x]
                        return

                # TODO check this
                process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_IN)

            return

        # Freq change events give the time at which a frequency change occured.
        # Can be later used to calculate workload/energy consumption of threads
        # in relation to the system configuration as they were executed.
        elif isinstance(event, EventFreqChange):
            # update cpu freq
            self.metrics.core_freqs[event.cpu] = event.freq
            # add event to cpu branch
            self.cpus[event.cpu].add_job(event)
            return

        elif isinstance(event, EventMaliUtil):

            self.metrics.gpu_freq = event.freq
            self.metrics.gpu_util = event.util

            self.gpu.add_job(event)

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
            if str(event.PID) in self.PIDt.allAppPIDStrings or \
                    str(event.PID) in self.PIDt.allSystemPIDStrings:
                process_branch = \
                    self.process_branches[self.PIDt.getPIDStringIndex(event.PID)]

                # Push binder event on to pending list so that when the second
                # half of the transaction is performed the events can be merged.
                # The first half should give the event PID and time stamp
                # The second half gives to_proc PID and recv_time timestamp
                self.pending_binder_transactions.append( \
                    PendingBinderTransaction(event, self.PIDt))

                # create binder send job in client thread tree (current tree)
                process_branch.add_job(event, event_type=JobType.BINDER_SEND)

                self.logger.debug("Binder event from: " + str(event.PID) + \
                                  " to " + str(event.dest_proc))

            # FROM BINDER THREAD TO SERVER PROC
            elif str(event.PID) in self.PIDt.allBinderPIDStrings:

                # get event from binder transactions list and merge
                if self.pending_binder_transactions:
                    process_branch = \
                        self.process_branches[self.PIDt.getPIDStringIndex(event.PID)]
                    for x, transaction in \
                            enumerate(self.pending_binder_transactions):

                        # If the binder thread that is completing the transaction
                        # is a child of a previous transactions parent binder PID
                        if any(pid == event.PID for pid in transaction.child_PIDs) or \
                                event.PID == transaction.parent_PID:
                            # Add job to the branch of the Binder thread
                            process_branch.add_job(event, event_type=JobType.BINDER_RECV)

                            # add pending task
                            self.pending_binder_tasks.append \
                                (PendingBinderTask(transaction.send_event, event))

                            # remove completed transaction
                            del self.pending_binder_transactions[x]
                            return
            else:
                print "Unhandled binder"
                # Find the unknown PID and add it to the system
                child_threads = adbInterface.current_interface.runCommand("busybox ps -T | grep " + str(event.PID))
                child_threads = child_threads.splitlines()
                for line in child_threads:
                    if "grep" not in line:
                        regex_find = re.findall("(\d+) \d+ +\d+:\d+ ({(.*)}.* )?(.+)$", line)
                        pid = int(regex_find[0][0])
                        pname = regex_find[0][3]
                        if not regex_find[0][2]:
                            tname = pname
                        else:
                            tname = regex_find[0][2]

                        # if the thread is new then save it
                        if not any(proc.pid == pid for proc in self.allSystemPID):
                            new_pid = PID(pid, pname, tname)
                            self.allSystemPID.append(new_pid)
                            self.allPid.append(new_pid)
                            self.allSystemPIDStrings.append(str(pid))
                            self.allPIDStrings.append(str(pid))

            return


        else:
            self.logger.debug("Unknown event")
