import logging

import networkx as nx
from aenum import Enum
from pydispatch import dispatcher
import dispatch
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

    def __init__(self, PID, time, cpu, freq, util, target_cpu):
        Event.__init__(self, PID, time, cpu, "freq change")
        self.freq = freq
        self.util = util
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


""" When calculating the power required for a task one needs to know the utilization
and frequency. The utilization can be assumed to not vary a significant amount during
the execution of a single job but the frequency should be tracked. A power chunk keeps
track of the frequency levels used during a job as well as the durations such that the
total duration of the job can later be divided into periods of different frequency
use 
"""
class FreqPowerEvent:
    # Frequency up until the event, not the frequency after the event
    def __init__(self, time, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util):
        self.time = time
        self.cpu = cpu
        self.cpu_frequency = cpu_freq
        self.gpu_frequency = gpu_freq
        self.cpu_util = cpu_util #not really needed
        self.gpu_util = gpu_util


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
    running or the GPU changes or the frequency changes then the variable is updated and
    the calc time shifted to the point of the event. As such the calc time stores the time since
    the exec time was last changed, and given that the CPU and frequency have been fixed during
    that time, the cycles is easily updated using a += and the current values (before updating them)
    """
    def __init__(self, graph, PID):
        self.events = []
        self.power_freq_events = []
        self.cpu_cycles = 0
        self.gpu_cycles = 0
        self.start_time = 0
        self.calc_time = 0
        self.energy = 0.0
        self.duration = 0
        self.finish_time = 0
        self.graph = graph
        self.PID = PID

    def get_cycle_energy(self, CPU, freq, utilization, gpu=False):
        try:
            if gpu:
                for x, entry in enumerate(SystemMetrics.current_metrics.energy_profile.gpu_values):
                    if entry.frequency == freq:
                        return entry.alpha * utilization + entry.beta
                return 0
            if CPU in range(4):
                for x, entry in enumerate(SystemMetrics.current_metrics.energy_profile.little_values):
                    if entry.frequency == freq:
                        return entry.alpha * utilization + entry.beta
                return 0
            else:
                for x, entry in enumerate(SystemMetrics.current_metrics.energy_profile.big_values):
                    if entry.frequency == freq:
                        return entry.alpha * utilization + entry.beta
                return 0
        except ValueError:
            print "invalid frequency"

    def add_job(self, event, binder_send=False):

        # First event
        if not self.events:
            self.start_time = event.time

        # Switching events
        if isinstance(event, EventSchedSwitch):
            # Switching out
            if event.PID == self.PID:
                # Calculate cycles
                if self.calc_time is 0:
                    self.calc_time = event.time

                if self.power_freq_events:
                    # Events are sequential in time
                    for x, pe in enumerate(self.power_freq_events):
                        if pe.time < self.events[-1].time:
                            # TODO might cause indexing errors
                            continue
                        # calc time is the point until which the cycles were last counted
                        #TODO reduce this
                        new_cycles = int((pe.time - self.calc_time) * 0.000001 * pe.cpu_frequency * 1000)
                        self.cpu_cycles += new_cycles
                        util = SystemMetrics.current_metrics.sys_util.get_util(pe.cpu, pe.time)
                        cycle_energy = self.get_cycle_energy(pe.cpu, pe.cpu_frequency, util)
                        self.energy += cycle_energy * new_cycles

                        self.duration += pe.time - self.calc_time
                        self.calc_time = pe.time
                    del self.power_freq_events[:]
                # remaining cycles
                if event.time != self.calc_time:
                    cpu_speed = SystemMetrics.current_metrics.get_CPU_core_freq(event.cpu)
                    gpu_speed = SystemMetrics.current_metrics.get_GPU_core_freq()

                    new_cycles = int((event.time - self.calc_time) * 0.000001 * cpu_speed * 1000)
                    self.cpu_cycles += new_cycles
                    util = SystemMetrics.current_metrics.sys_util.get_util(event.cpu, event.time)
                    cycle_energy = self.get_cycle_energy(event.cpu, cpu_speed, util)

                    self.energy += cycle_energy * new_cycles
                    self.duration += event.time - self.calc_time
                    self.calc_time = event.time


            # Switching in
            if event.next_pid == self.PID:

                # when this slice is switched out we want to append only cycles for this slice
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
        elif isinstance(event, EventBinderCall) and binder_send is False:
            self.graph.add_node(event, label=str(event.time)[:-6] + "." + str(event.time)[-6:] +
                                             " CPU: " + str(event.cpu) + "\n" + str(event.PID)
                                             + " ==> " + str(event.dest_proc)
                                             + "\n" + str(event.name)
                                             + "\n" + str(event.__class__.__name__)
                                , fillcolor='aquamarine1', style='filled', shape='box')

        # create graph edge if not the first job
        if len(self.events) >= 2 and binder_send is False:
            self.graph.add_edge(self.events[-2], self.events[-1], color='violet', dir='forward')

    def finished(self):
        self.finish_time = self.events[-1].time

    def add_cpu_gpu_event(self, time, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util):
        self.power_freq_events.append(FreqPowerEvent(time, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util))


class BinderNode(TaskNode):

    def __init__(self, graph, PID):
        TaskNode.__init__(self, graph, PID)


class CPUBranch:

    def __init__(self, cpu_number, initial_freq, initial_util, graph):
        self.cpu_num = cpu_number
        self.freq = initial_freq
        self.prev_freq = initial_freq
        self.util = initial_util
        self.prev_util = initial_util
        self.events = []
        self.graph = graph
        self.signal_freq = "freq_change" + str(self.cpu_num)

    def send_change_event(self):
        dispatcher.send(signal=self.signal_freq, sender=dispatcher.Any)

    def add_job(self, event):

        self.events.append(event)

        # Update current frequency
        if event.freq != self.freq or event.util != self.util:
            self.prev_freq = self.freq
            self.freq = event.freq

            if self.util is 0:
                self.prev_util = event.util
            else:
                self.prev_util = self.util
            self.util = event.util

            self.send_change_event()


        self.graph.add_node(self.events[-1],
                            label=str(self.events[-1].time)[:-6] + "." + str(self.events[-1].time)[-6:]
                                  + "\nCPU: " + str(event.cpu) + " Util: " + str(event.util)
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
        self.signal_change = "gpu_change"

    def send_change_event(self):
        dispatcher.send(signal=self.signal_change, sender=dispatcher.Any)

    def add_job(self, event):

        self.events.append(event)

        if event.freq != self.freq or event.util != self.util:
            self.prev_freq = self.freq
            self.freq = event.freq

            if self.util is 0:
                self.prev_util = event.util
            else:
                self.prev_util = self.util
            self.util = event.util

            self.send_change_event()

        self.graph.add_node(self.events[-1],
                            label=str(self.events[-1].time)[:-6] + "." + str(self.events[-1].time)[-6:]
                                    + "\nUtil: " + str(self.events[-1].util)
                                    + "\nFreq: " + str(self.events[-1].freq)
                                    + "\n" + str(self.events[-1].__class__.__name__),
                                    style='filled',
                                    shape='box', fillcolor='magenta')

    # self.gpu_cycles += int((event.time - self.calc_time) * 0.000001 * gpu_speed * 1000000)


class ProcessBranch:
    """
    Events must be added to the "branch" of their PID. The data is processed
    such that each PID runs down a single file branch that is then branched out
    of and into to represent IPCs. The tree consists of tasks, each task being
    comprised of jobs/slices (time spend executing thread between a wake and
    sleep event).
    """

    def __init__(self, pid, start, graph, PIDt, CPUs, GPU):
        self.PID = pid
        self.tasks = []
        self.start = start
        self.active = False
        self.graph = graph
        self.PIDt = PIDt
        self.CPU = None
        self.CPUs = CPUs
        self.gpu = GPU
        self.connect_to_gpu_events()

    def connect_to_cpu_event(self, cpu):
        dispatcher.connect(self.handle_cpu_freq_change, signal=self.CPUs[cpu].signal_freq,
                            sender=dispatcher.Any)

    def disconnect_from_cpu_event(self, cpu):
        try:
            dispatcher.disconnect(self.handle_cpu_freq_change, signal=self.CPUs[cpu].signal_freq,
                                sender=dispatcher.Any)
        except Exception:
            return

    def connect_to_gpu_events(self):
        dispatcher.connect(self.handle_gpu_change, signal=self.gpu.signal_change,
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

    def handle_cpu_freq_change(self, event):
        if self.tasks:
            try:
                self.tasks[-1].add_cpu_gpu_event(self.CPUs[self.CPU].events[-1].time,
                                                 self.CPU,
                                                 self.CPUs[self.CPU].prev_freq,
                                                 self.CPUs[self.CPU].prev_util,
                                                 self.gpu.freq,
                                                 self.gpu.util)
            except Exception:
                pass

    def handle_cpu_num_change(self, event):
        # If the new CPU freq is different create change event for later calculations
        if self.tasks:
            try:
                if self.CPUs[event.cpu].freq != self.CPUs[self.CPU].freq:
                    self.tasks[-1].add_cpu_gpu_event(event.time,
                                                     self.CPU,
                                                    self.CPUs[self.CPU].freq,
                                                    self.CPUs[self.CPU].util,
                                                    self.gpu.freq,
                                                    self.gpu.util)
            except Exception:
                pass

        self.CPU = event.cpu

    def handle_gpu_change(self):
        return
        # if self.tasks:
        #     try:
        #         #TODO GPU POWER
        #         # self.tasks[-1].add_cpu_gpu_event(self.gpu.events[-1].time,
        #         #                                  self.CPU,
        #         #                                  self.CPUs[self.CPU].freq,
        #         #                                  self.CPUs[self.CPU].util,
        #         #                                  self.gpu.prev_freq,
        #         #                                  self.gpu.prev_util)
        #     except Exception:
        #         pass

    def add_job(self, event, event_type=JobType.UNKNOWN):

        # CPU association
        if self.CPU is None:
            self.CPU = event.cpu
            self.connect_to_cpu_event(self.CPU)

        # first job/task for PID branch
        if not self.tasks:

            self.tasks.append(TaskNode(self.graph, self.PID))
            self.tasks[-1].add_job(event)

            # task could be finishing
            if event_type == JobType.SCHED_SWITCH_OUT and \
                    event.prev_state == ThreadState.INTERRUPTIBLE_SLEEP_S.value:
                self.active = False
                self.tasks[-1].finished()

                #TODO ADD NODE HERE
                return

            self.active = True

            return

        if event_type == JobType.SCHED_SWITCH_IN:
            # If the CPU has changed
            if event.cpu != self.CPU:
                # Update current task's cycle count in case new CPU has different speed
                self.handle_cpu_num_change(event)

                # Change event signal for freq change
                self.disconnect_from_cpu_event(self.CPU)
                self.CPU = event.cpu
                self.connect_to_cpu_event(self.CPU)


        # New task STARTING
        if event_type == JobType.SCHED_SWITCH_IN and self.active is False:

            # create new task
            self.tasks.append(TaskNode(self.graph, self.PID))
            # add current event
            self.tasks[-1].add_job(event)

            # set task to running
            self.active = True

            # These edges simply follow a PID, do not show any IPCs or IPDs
            if len(self.tasks) >= 2:
                self.graph.add_edge(self.tasks[-2], self.tasks[-1], color='lightseagreen',
                                    style='dashed')

            return

        # Current task FINISHING
        elif event_type == JobType.SCHED_SWITCH_OUT and \
                event.prev_state == ThreadState.INTERRUPTIBLE_SLEEP_S.value and \
                str(event.PID) not in self.PIDt.allBinderPIDStrings:

            self.tasks[-1].add_job(event)
            self.tasks[-1].finished()
            self.active = False

            self.graph.add_node(self.tasks[-1],
                                label=str(self.tasks[-1].start_time)[:-6] + "."
                                    + str(self.tasks[-1].start_time)[-6:]
                                    + " ==> " + str(self.tasks[-1].finish_time)[:-6] + "."
                                    + str(self.tasks[-1].finish_time)[-6:]
                                    + "\nCPU: " + str(event.cpu) + "   PID: " + str(event.PID)
                                    + "\nGPU: " + str(SystemMetrics.current_metrics.gpu_freq) + "MHz   "
                                    + str(SystemMetrics.current_metrics.gpu_util) + "% Util"
                                    + "\nDuration: " + str(self.tasks[-1].duration)
                                    + "\nCPU Cycles: " + str(self.tasks[-1].cpu_cycles)
                                    + "\nEnergy: " + str(self.tasks[-1].energy)
                                    + "\n" + str(event.name)
                                    + "\n" + str(self.tasks[-1].__class__.__name__),
                                fillcolor='darkolivegreen3',
                                style='filled,bold,rounded', shape='box')

            # Jobs sub-graph
            self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[0], color='blue',
                                dir='forward')
            self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[-1], color='red',
                                dir='back')
            return

        elif event_type == JobType.BINDER_SEND:
            self.tasks.append(BinderNode(self.graph, self.PID))
            self.tasks[-1].add_job(event, binder_send=True)
            return

        elif event_type == JobType.BINDER_RECV:

            self.tasks[-1].add_job(event)
            self.tasks[-1].finished()

            self.graph.add_node(self.tasks[-1],
                                label=
                                    str(self.tasks[-1].events[0].time)[:-6]
                                    + "." + str(self.tasks[-1].events[0].time)[-6:]
                                    + " ; " + str(self.tasks[-1].events[-1].time)[:-6]
                                    + "." + str(self.tasks[-1].events[-1].time)[-6:]
                                    + "\npid: " + str(event.PID)
                                    + "  dest PID: " + str(event.dest_proc)
                                    + "\n" + str(event.name)
                                    + "\n" + str(self.tasks[-1].__class__.__name__),
                                fillcolor='coral', style='filled,bold', shape='box')
            return

        # all other job types just need to get added to the task
        self.tasks[-1].add_job(event)


""" Binder transactions are sometimes directed to the parent binder thread of a
system service. The exact PID of the child thread is not known when the
transaction is done. A list of open transaction is to be maintained where each
entry shows possible child thread PID that could appear in the corresponding
wake event. Allowing binder transactions to be matched to their corresponding
wake event.
"""

class PendingBinderTransaction:

    def __init__(self, event, PIDt):
        self.parent_PID = event.dest_proc
        if str(event.dest_proc) in PIDt.allBinderPIDStrings:
            self.child_PIDs = [event.dest_proc]
        else:
            self.child_PIDs = PIDt.find_child_binder_threads(event.dest_proc)
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
                            format='%(asctime)s %(levelname)s:%(message)s',
                            level=logging.DEBUG)
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
                                       self.metrics.core_utils[x], self.graph))

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
            index = self.PIDt.get_PID_string_index(event.PID)
            if index is not None and index != 0:
                process_branch = self.process_branches[index]
                process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_OUT)
                self.logger.debug("Sched switch in event added as job")
                return

            # task being switched in
            index = self.PIDt.get_PID_string_index(event.next_pid)
            if index is not None and index != 0:
                process_branch = self.process_branches[index]

                # if switched in because of binder
                for x, task in enumerate(self.pending_binder_tasks):
                    if event.next_pid == task.dest_pid:

                        # edge from prev task to binder thread
                        self.graph.add_edge(
                            # original process branch that started transaction
                            self.process_branches[ \
                                self.PIDt.get_PID_string_index(task.from_pid)].tasks[-1],
                            # this branch as it is being woken
                            self.process_branches[ \
                                self.PIDt.get_PID_string_index(task.binder_thread)].tasks[-1],
                            color='palevioletred3', dir='forward', style='bold')

                        process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_IN)

                        # edge from binder thread to next task
                        self.graph.add_edge(
                            # original process branch that started transaction
                            self.process_branches[ \
                                self.PIDt.get_PID_string_index(task.binder_thread)].tasks[-1],
                            # this branch as it is being woken
                            self.process_branches[ \
                                self.PIDt.get_PID_string_index(task.dest_pid)].tasks[-1],
                            color='yellow3', dir='forward')

                        # remove binder task that is now complete
                        del self.pending_binder_tasks[x]
                        return

                process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_IN)

            return

        elif isinstance(event, EventFreqChange):
            # update cpu freq
            self.metrics.core_freqs[event.target_cpu] = event.freq
            self.metrics.core_utils[event.target_cpu] = event.util
            # add event to cpu branch
            self.cpus[event.target_cpu].add_job(event)
            return

        elif isinstance(event, EventMaliUtil):

            self.metrics.gpu_freq = event.freq
            self.metrics.gpu_util = event.util

            self.gpu.add_job(event)

        # Also used in the calculation of system load
        elif isinstance(event, EventIdle):
            self.metrics.sys_util.core_utils[event.cpu].add_event(event)
            return

        # Binder transactions show IPCs between tasks.
        # As a binder transaction represents the blocking of the client task
        # the transactions are processed as sleep events for the client tasks.
        # Binder transactions happen in two parts, they send to a binder thread
        # then the tread sends to the target task. As such binder transactions
        # are identified by if they send or recv from a binder thread then
        # handled accordingly
        elif isinstance(event, EventBinderCall):

            # From client process to binder thread
            if str(event.PID) in self.PIDt.allAppPIDStrings or \
                    str(event.PID) in self.PIDt.allSystemPIDStrings:
                process_branch = \
                    self.process_branches[self.PIDt.get_PID_string_index(event.PID)]

                # Push binder event on to pending list so that when the second
                # half of the transaction is performed the events can be merged.
                # The first half should give the event PID and time stamp
                # The second half gives to_proc PID and recv_time timestamp
                self.pending_binder_transactions.append( \
                    PendingBinderTransaction(event, self.PIDt))

                # create binder send job in client thread tree (current tree)
                # process_branch.add_job(event, event_type=JobType.BINDER_SEND)

                self.logger.debug("Binder event from: " + str(event.PID) + \
                                  " to " + str(event.dest_proc))

            # from binder thread to target server process
            elif str(event.PID) in self.PIDt.allBinderPIDStrings:

                # get event from binder transactions list and merge
                if self.pending_binder_transactions:
                    process_branch = \
                        self.process_branches[self.PIDt.get_PID_string_index(event.PID)]
                    for x, transaction in \
                            enumerate(self.pending_binder_transactions):

                        # If the binder thread that is completing the transaction
                        # is a child of a previous transactions parent binder PID
                        if any(pid == event.PID for pid in transaction.child_PIDs) or \
                                event.PID == transaction.parent_PID:

                            # Add starting binder event to branch
                            process_branch.add_job(transaction.send_event, event_type=JobType.BINDER_SEND)

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
                # Find the unknown PID and add it to the system if possible
                # child_threads = adbInterface.current_interface.run_command("busybox ps -T | grep " + str(event.PID))
                # child_threads = child_threads.splitlines()
                # for line in child_threads:
                #     if "grep" not in line:
                #         regex_find = re.findall("(\d+) \d+ +\d+:\d+ ({(.*)}.* )?(.+)$", line)
                #         pid = int(regex_find[0][0])
                #         pname = regex_find[0][3]
                #         if not regex_find[0][2]:
                #             tname = pname
                #         else:
                #             tname = regex_find[0][2]
                #
                #         # if the thread is new then save it
                #         if not any(proc.pid == pid for proc in self.allSystemPID):
                #             new_pid = PID(pid, pname, tname)
                #             self.allSystemPID.append(new_pid)
                #             self.allPid.append(new_pid)
                #             self.allSystemPIDStrings.append(str(pid))
                #             self.allPIDStrings.append(str(pid))

            return

        else:
            self.logger.debug("Unknown event")