import csv
import time
import networkx as nx
from aenum import Enum
from pydispatch import dispatcher

from adbinterface import *
from metrics import SystemMetrics

PL_PID = 'PID'
PL_PID_PNAME = 'PNAME'
PL_PID_TNAME = 'TNAME'
PL_TASK_COUNT = 'TASK COUNT'
PL_ENERGY = 'ENERGY [J]'
PL_DURATION = 'DURATION [nS]'


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

    def __init__(self, PID, time, cpu, name, reply, dest_pid, flags, code):
        Event.__init__(self, PID, time, cpu, name)
        if reply == 0:
            if flags & 0b1:
                self.trans_type = BinderType.ASYNC
            else:
                self.trans_type = BinderType.CALL
        elif reply == 1:
            self.trans_type = BinderType.REPLY
        else:
            self.trans_type = BinderType.UNKNOWN
        self.dest_pid = dest_pid
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
        self.cpu_util = cpu_util  # not really needed
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
        self.temp = 0
        self.util = 0

    def get_CPU_per_second_energy(self, CPU, freq, util, temp):
        try:
            EP = SystemMetrics.current_metrics.energy_profile
            if CPU in range(4):
                voltage = EP.little_voltages[freq]
                a1 = EP.little_reg_const["a1"]
                a2 = EP.little_reg_const["a2"]
                a3 = EP.little_reg_const["a3"]
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
                return energy
            else:
                voltage = EP.big_voltages[freq]
                a1 = EP.big_reg_const["a1"]
                a2 = EP.big_reg_const["a2"]
                a3 = EP.big_reg_const["a3"]
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
                return energy
        except ValueError:
            print "invalid frequency"
        except TypeError:
            print "Type error"

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
                        # TODO reduce this

                        new_cycles = int((pe.time - self.calc_time) * 0.000000001 * pe.cpu_frequency)
                        self.util = SystemMetrics.current_metrics.sys_util.core_utils[pe.cpu].get_util(pe.time)
                        self.temp = SystemMetrics.current_metrics.get_temp(pe.time, pe.cpu)

                        cycle_energy = self.get_CPU_per_second_energy(pe.cpu, pe.cpu_frequency, self.util,
                                                                      self.temp) / pe.cpu_frequency
                        self.cpu_cycles += new_cycles
                        self.energy += cycle_energy * new_cycles
                        self.duration += pe.time - self.calc_time
                        self.calc_time = pe.time

                    del self.power_freq_events[:]
                # remaining cycles
                if event.time != self.calc_time:
                    cpu_speed = SystemMetrics.current_metrics.get_CPU_core_freq(event.cpu)

                    new_cycles = int((event.time - self.calc_time) * 0.000000001 * cpu_speed)
                    self.util = SystemMetrics.current_metrics.sys_util.core_utils[event.cpu].get_util(event.time)
                    self.temp = SystemMetrics.current_metrics.get_temp(event.time, event.cpu)

                    cycle_energy = self.get_CPU_per_second_energy(event.cpu, cpu_speed, self.util,
                                                                  self.temp) / cpu_speed

                    self.cpu_cycles += new_cycles
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
                                             + " ==> " + str(event.dest_pid)
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

        # Update metrics and energy usage

        self.graph.add_node(self.events[-1],
                            label=str(self.events[-1].time)[:-6] + "." + str(self.events[-1].time)[-6:]
                                  + "\nUtil: " + str(self.events[-1].util)
                                  + "\nFreq: " + str(self.events[-1].freq)
                                  + "\n" + str(self.events[-1].__class__.__name__),
                            style='filled',
                            shape='box', fillcolor='magenta')


class EnergyDuration:

    def __init__(self):
        self.energy = 0
        self.duration = 0


class ProcessBranch:
    """
    Events must be added to the "branch" of their PID. The data is processed
    such that each PID runs down a single file branch that is then branched out
    of and into to represent IPCs. The tree consists of tasks, each task being
    comprised of jobs/slices (time spend executing thread between a wake and
    sleep event).
    """

    def __init__(self, pid, pname, tname, start, graph, PIDt, CPUs, GPU):
        self.PID = pid
        self.pname = pname
        self.tname = tname
        self.tasks = []
        self.start = start
        self.active = False
        self.graph = graph
        self.PIDt = PIDt
        self.CPU = None
        self.CPUs = CPUs
        self.gpu = GPU
        self.connect_to_gpu_events()
        self.energy = 0  # calculated upon request at the end between given intervals
        self.duration = 0

    def get_second_energy(self, second, time_offset):
        energy = 0.0
        nanosecond_start = time_offset + (second * 1000000)
        nanosecond_finish = nanosecond_start + 1000000
        # Find task that contains the start of the second of interest
        for task in self.tasks:
            if isinstance(task, EventBinderCall) or isinstance(task, BinderNode):
                continue
            # Task that falls at starting point
            if (task.start_time <= nanosecond_start) and (task.finish_time > nanosecond_start):
                try:
                    energy += (task.finish_time - nanosecond_start) / task.duration * task.energy
                except ZeroDivisionError:
                    continue
            # Task that falls at the ending of the second
            elif (task.start_time <= nanosecond_finish) and (nanosecond_finish < task.finish_time):
                try:
                    energy += (nanosecond_finish - task.start_time) / task.duration * task.energy
                except ZeroDivisionError:
                    continue
            elif (task.start_time > nanosecond_start) and (task.finish_time < nanosecond_finish):
                energy += task.energy
        return energy

    def _sum_stats_until_finish(self, start_event_index, finish_time):
        task_stats = EnergyDuration()
        if finish_time == 0:
            for task in self.tasks:
                task_stats.energy += task.energy
                task_stats.duration += task.duration
        else:
            for x, task in enumerate(self.tasks[start_event_index:-1]):
                if finish_time < self.tasks[x + 1]:
                    # calculate % of energy to take
                    percent = ((finish_time - task.time) / task.duration)
                    task_stats.energy += percent * task.energy
                    task_stats.duration += percent * task.duration
                else:
                    task_stats.energy += task.energy
                    task_stats.duration += task.duration
        return task_stats

    def sum_task_stats(self, start_time, finish_time):
        task_stats = EnergyDuration()
        if start_time == 0:
            # sum all events
            end_stats = self._sum_stats_until_finish(0, finish_time)
            task_stats.energy += end_stats.energy
            task_stats.duration += end_stats.duration
        else:
            # find first task and get the partial sum
            for x, task in enumerate(self.tasks):
                if (start_time > task.start_time) and (start_time < (task.start_time + task.duration)):
                    percent = (((task.start_time + task.duration) - start_time) / task.duration)
                    task_stats.energy += percent * task.energy
                    task_stats.duration += percent * task.duration
                elif start_time < task.start_time:
                    end_stats = self._sum_stats_until_finish(x, finish_time)
                    task_stats.energy += end_stats.energy
                    task_stats.duration += end_stats.duration
                    return task_stats
        return task_stats

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

    def handle_cpu_freq_change(self):
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

                # TODO ADD NODE HERE
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
                event.PID not in self.PIDt.allBinderPIDStrings:

            self.tasks[-1].add_job(event)
            self.tasks[-1].finished()
            self.active = False

            self.graph.add_node(self.tasks[-1],
                                label=str(self.tasks[-1].start_time)[:-6] + "."
                                      + str(self.tasks[-1].start_time)[-6:]
                                      + " ==> " + str(self.tasks[-1].finish_time)[:-6] + "."
                                      + str(self.tasks[-1].finish_time)[-6:]
                                      + "\nCPU: " + str(event.cpu)
                                      + "   Util: " + str(self.tasks[-1].util) + "%"
                                      + "   Temp: " + str(self.tasks[-1].temp)
                                      + "   PID: " + str(event.PID)
                                      + "\nGPU: " + str(SystemMetrics.current_metrics.gpu_freq) + "Hz   "
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
                                + "  dest PID: " + str(event.dest_pid)
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
        self.parent_PID = event.dest_pid
        if event.dest_pid in PIDt.allBinderPIDStrings:
            self.child_PIDs = event.dest_pid
        else:
            self.child_PIDs = PIDt.find_child_binder_threads(event.dest_pid)
        self.send_event = event


class PendingBinderTask:

    def __init__(self, from_event, dest_event):
        self.from_pid = from_event.PID
        self.dest_pid = dest_event.dest_pid
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

        for pid in self.PIDt.allPID:
            self.process_branches.append(ProcessBranch(pid.pid, pid.pname, pid.tname, None, self.graph,
                                                       self.PIDt, self.cpus, self.gpu))

        for x in range(0, self.metrics.core_count):
            self.cpus.append(CPUBranch(x, self.metrics.core_freqs[x],
                                       self.metrics.core_utils[x], self.graph))

    def finish_tree(self, start_time, finish_time, filename):
        with open(filename + "_results.csv", "w+") as f:
            writer = csv.writer(f, delimiter=',')

            # Start and end time
            start_time = 0
            end_time = 0
            for branch in self.process_branches:
                if branch.tasks:
                    if branch.tasks[0].start_time < start_time or start_time == 0:
                        start_time = branch.tasks[0].start_time
                    if (branch.tasks[-1].start_time + branch.tasks[-1].duration) > end_time or end_time == 0:
                        end_time = branch.tasks[-1].start_time + branch.tasks[-1].duration

            writer.writerow(["Start", start_time/1000000.0])
            writer.writerow(["Finish", end_time/1000000.0])
            duration = (end_time - start_time) * 0.000001
            writer.writerow(["Duration", duration])

            writer.writerow([PL_PID, PL_PID_PNAME, PL_PID_TNAME, PL_TASK_COUNT,
                             PL_ENERGY, PL_DURATION])

            total_energy = 0;

            # Calculate GPU energy
            GPU_energy = self.metrics.sys_util.gpu_utils.calc_GPU_power(0,0)
            writer.writerow(["GPU", GPU_energy])

            total_energy += GPU_energy

            for x in range(len(self.process_branches) - 1, -1, -1):
                branch = self.process_branches[x]
                # Remove empty PID branches
                if branch.tasks == []:
                    del self.process_branches[x]
                    continue
                branch_stats = branch.sum_task_stats(start_time, finish_time)
                branch.energy = branch_stats.energy
                total_energy += branch.energy
                branch.duration = branch_stats.duration

                # Write results to file
                writer.writerow([branch.PID, branch.pname, branch.tname, str(len(branch.tasks)),
                                 branch.energy, branch.duration])
            writer.writerow([])
            writer.writerow(["Total Energy", total_energy])
            writer.writerow(["Average wattage", total_energy/duration])

            # Go through each branch and calculate the values energy values for each second
            energy_timeline = [0.0] * int(duration + 1)

            for branch in self.process_branches:
                for x in range(len(energy_timeline)):
                    energy_timeline[x] += branch.get_second_energy(x, start_time)

            writer.writerow(["Sec", "Energy"])
            for x, second in enumerate(energy_timeline):
                writer.writerow([str(x), str(second)])


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
            if event.cpu == 0:
                for i in range(4):
                    self.metrics.core_freqs[i] = event.freq
                    self.metrics.core_utils[i] = event.util
                    self.cpus[i].add_job(event)
            else:
                for i in range(4):
                    self.metrics.core_freqs[i+1] = event.freq
                    self.metrics.core_utils[i+1] = event.util
                    self.cpus[i+4].add_job(event)

            return

        elif isinstance(event, EventMaliUtil):

            self.metrics.gpu_freq = event.freq
            self.metrics.gpu_util = event.util

            self.metrics.sys_util.gpu_utils.add_mali_event(event)

            self.gpu.add_job(event)

        # Also used in the calculation of system load
        elif isinstance(event, EventIdle):
            self.metrics.sys_util.core_utils[event.cpu].add_idle_event(event)
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
            if event.PID in self.PIDt.allAppPIDStrings or \
                    event.PID in self.PIDt.allSystemPIDStrings:

                # TODO sometimes binder transactions are sent to binder threads without a target
                #  process. I am unsure what purpose this serves
                if event.dest_pid in self.PIDt.allBinderPIDStrings:
                    return

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
                                  " to " + str(event.dest_pid))

            # from binder thread to target server process
            elif event.PID in self.PIDt.allBinderPIDStrings:

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

            return

        else:
            self.logger.debug("Unknown event")
