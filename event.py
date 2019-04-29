import networkx as nx
from pydispatch import dispatcher

from metrics import *

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


class Event:

    def __init__(self, pid, ts, cpu, name):
        self.pid = pid
        self.time = ts
        self.cpu = cpu
        self.name = name


class EventSchedSwitch(Event):

    def __init__(self, pid, ts, cpu, name, prev_state, next_pid, next_name):
        Event.__init__(self, pid, ts, cpu, name)
        self.prev_state = prev_state
        self.next_pid = next_pid
        self.next_name = next_name


class EventFreqChange(Event):

    def __init__(self, pid, ts, cpu, freq, util, target_cpu):
        Event.__init__(self, pid, ts, cpu, "freq change")
        self.freq = freq
        self.util = util
        self.target_cpu = target_cpu


class EventWakeup(Event):

    def __init__(self, pid, ts, cpu, name):
        Event.__init__(self, pid, ts, cpu, name)


class EventIdle(Event):

    def __init__(self, ts, cpu, name, state):
        Event.__init__(self, 0, ts, cpu, name)
        self.state = state


class EventBinderCall(Event):

    def __init__(self, pid, ts, cpu, name, reply, dest_pid, flags, code):
        Event.__init__(self, pid, ts, cpu, name)
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

    def __init__(self, pid, ts, cpu, util, freq):
        Event.__init__(self, pid, ts, cpu, "mali util")
        self.util = util
        self.freq = freq


class EventTempInfo(Event):

    def __init__(self, ts, cpu, big0, big1, big2, big3, gpu):
        Event.__init__(self, 0, ts, cpu, "temp")
        self.big0 = big0
        self.big1 = big1
        self.big2 = big2
        self.big3 = big3
        self.little = (big0 + big1 + big2 + big3) / 4.0
        self.gpu = gpu


""" When calculating the power required for a task one needs to know the utilization
and frequency. The utilization can be assumed to not vary a significant amount during
the execution of a single job but the frequency should be tracked. A power chunk keeps
track of the frequency levels used during a job as well as the durations such that the
total duration of the job can later be divided into periods of different frequency
use 
"""


class FreqPowerEvent:
    # Frequency up until the event, not the frequency after the event
    def __init__(self, ts, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util):
        self.time = ts
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

    def __init__(self, graph, pid):
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
        self.pid = pid
        self.temp = 0
        self.util = 0

    def get_CPU_per_second_energy(self, cpu, freq, util, temp):
        try:
            energy_profile = SystemMetrics.current_metrics.energy_profile
            voltage = 0
            if cpu in range(4):
                try:
                    voltage = energy_profile.little_voltages[freq]
                except Exception:
                    print str(cpu)
                a1 = energy_profile.little_reg_const["a1"]
                a2 = energy_profile.little_reg_const["a2"]
                a3 = energy_profile.little_reg_const["a3"]
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
                return energy
            else:
                try:
                    voltage = energy_profile.big_voltages[freq]
                except Exception:
                    print str(cpu)
                a1 = energy_profile.big_reg_const["a1"]
                a2 = energy_profile.big_reg_const["a2"]
                a3 = energy_profile.big_reg_const["a3"]
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
                return energy
        except ValueError:
            print "invalid frequency"
        except TypeError:
            print "Type error"

    def add_job(self, event, binder_send=False, subgraph=False):

        # First event
        if not self.events:
            self.start_time = event.time

        # Switching events
        if isinstance(event, EventSchedSwitch):
            # Switching out
            if event.pid == self.pid:
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
            if event.next_pid == self.pid:
                # when this slice is switched out we want to append only cycles for this slice
                self.calc_time = event.time

        # save event to parent task
        self.events.append(event)

        # add event node to task sub-graph
        if subgraph:
            if isinstance(event, EventSchedSwitch):
                self.graph.add_node(event, label=str(event.time)[:-6] + "." + str(event.time)[-6:] +
                                                 " CPU: " + str(event.cpu) + "\n" + str(event.pid)
                                                 + " ==> " + str(event.next_pid)
                                                 + "\nPrev state: " + str(event.prev_state)
                                                 + "\n" + event.name + " --> " + event.next_name + "\n"
                                                 + str(event.__class__.__name__),
                                    fillcolor='bisque1', style='filled', shape='box')
            elif isinstance(event, EventBinderCall) and binder_send is False:
                self.graph.add_node(event, label=str(event.time)[:-6] + "." + str(event.time)[-6:] +
                                                 " CPU: " + str(event.cpu) + "\n" + str(event.pid)
                                                 + " ==> " + str(event.dest_pid)
                                                 + "\n" + str(event.name)
                                                 + "\n" + str(event.__class__.__name__),
                                    fillcolor='aquamarine1', style='filled', shape='box')

            # create graph edge if not the first job
            if len(self.events) >= 2 and binder_send is False:
                if self.events[-2] == self.events[-1]:
                    print "wait here"
                self.graph.add_edge(self.events[-2], self.events[-1], color='violet', dir='forward')

    def finished(self):
        self.finish_time = self.events[-1].time

    def add_cpu_gpu_event(self, ts, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util):
        self.power_freq_events.append(FreqPowerEvent(ts, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util))


class BinderNode(TaskNode):

    def __init__(self, graph, pid):
        TaskNode.__init__(self, graph, pid)


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

    def __init__(self, pid, pname, tname, start, graph, pidtracer, cpus, gpu):
        self.pid = pid
        self.pname = pname
        self.tname = tname
        self.tasks = []
        self.start = start
        self.active = False
        self.graph = graph
        self.pidtracer = pidtracer
        self.cpu = None
        self.cpus = cpus
        self.gpu = gpu
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
        try:
            dispatcher.connect(self.handle_cpu_freq_change, signal=self.cpus[cpu].signal_freq,
                               sender=dispatcher.Any)
        except Exception:
            print "wait here"

    def disconnect_from_cpu_event(self, cpu):
        try:
            dispatcher.disconnect(self.handle_cpu_freq_change, signal=self.cpus[cpu].signal_freq,
                                  sender=dispatcher.Any)
        except Exception:
            return

    def connect_to_gpu_events(self):
        dispatcher.connect(self.handle_gpu_change, signal=self.gpu.signal_change,
                           sender=dispatcher.Any)

    def get_cur_cpu_freq(self):
        return self.cpus[self.cpu].freq

    def get_cur_cpu_prev_freq(self):
        return self.cpus[self.cpu].prev_freq

    def get_cur_cpu_last_freq_switch(self):
        if self.cpus[self.cpu].events:
            return self.cpus[self.cpu].events[-1].time
        else:
            return None

    def handle_cpu_freq_change(self):
        if self.tasks:
            try:
                self.tasks[-1].add_cpu_gpu_event(self.cpus[self.cpu].events[-1].time,
                                                 self.cpu,
                                                 self.cpus[self.cpu].prev_freq,
                                                 self.cpus[self.cpu].prev_util,
                                                 self.gpu.freq,
                                                 self.gpu.util)
            except Exception:
                pass

    def handle_cpu_num_change(self, event):
        # If the new CPU freq is different create change event for later calculations
        if self.tasks:
            try:
                if self.cpus[event.cpu].freq != self.cpus[self.cpu].freq:
                    self.tasks[-1].add_cpu_gpu_event(event.time,
                                                     self.cpu,
                                                     self.cpus[self.cpu].freq,
                                                     self.cpus[self.cpu].util,
                                                     self.gpu.freq,
                                                     self.gpu.util)
            except Exception:
                pass

        self.cpu = event.cpu

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

    def add_job(self, event, event_type=JobType.UNKNOWN, subgraph=False):

        # CPU association
        if self.cpu is None:
            self.cpu = event.cpu
            self.connect_to_cpu_event(self.cpu)

        # first job/task for PID branch
        if not self.tasks:

            self.tasks.append(TaskNode(self.graph, self.pid))
            self.tasks[-1].add_job(event, subgraph=subgraph)

            # task could be finishing
            if event_type == JobType.SCHED_SWITCH_OUT and \
                    event.prev_state == ThreadState.INTERRUPTIBLE_SLEEP_S.value:
                self.active = False
                self.tasks[-1].finished()
                return

            self.active = True

            return

        if event_type == JobType.SCHED_SWITCH_IN:
            # If the CPU has changed
            if event.cpu != self.cpu:
                # Update current task's cycle count in case new CPU has different speed
                self.handle_cpu_num_change(event)

                # Change event signal for freq change
                self.disconnect_from_cpu_event(self.cpu)
                self.cpu = event.cpu
                self.connect_to_cpu_event(self.cpu)

        # New task STARTING
        if event_type == JobType.SCHED_SWITCH_IN and self.active is False:

            # create new task
            self.tasks.append(TaskNode(self.graph, self.pid))
            # add current event
            self.tasks[-1].add_job(event, subgraph=subgraph)

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
                event.pid not in self.pidtracer.binder_pids:

            self.tasks[-1].add_job(event, subgraph=subgraph)
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
                                      + "   PID: " + str(event.pid)
                                      + "\nGPU: " + str(SystemMetrics.current_metrics.gpu_freq) + "Hz   "
                                      + str(SystemMetrics.current_metrics.gpu_util) + "% Util"
                                      + "\nDuration: " + str(self.tasks[-1].duration)
                                      + "\nCPU Cycles: " + str(self.tasks[-1].cpu_cycles)
                                      + "\nEnergy: " + str(self.tasks[-1].energy)
                                      + "\n" + str(event.name)
                                      + "\n" + str(self.tasks[-1].__class__.__name__),
                                fillcolor='darkolivegreen3',
                                style='filled,bold,rounded', shape='box')

            if subgraph:
                # Jobs sub-graph
                self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[0], color='blue',
                                    dir='forward')
                self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[-1], color='red',
                                    dir='back')
            return

        elif event_type == JobType.BINDER_SEND:
            self.tasks.append(BinderNode(self.graph, self.pid))
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
                                + "\npid: " + str(event.pid)
                                + "  dest PID: " + str(event.dest_pid)
                                + "\n" + str(event.name)
                                + "\n" + str(self.tasks[-1].__class__.__name__),
                                fillcolor='coral', style='filled,bold', shape='box')
            return

        # all other job types just need to get added to the task
        self.tasks[-1].add_job(event, subgraph=subgraph)


""" Binder transactions are sometimes directed to the parent binder thread of a
system service. The exact PID of the child thread is not known when the
transaction is done. A list of open transaction is to be maintained where each
entry shows possible child thread PID that could appear in the corresponding
wake event. Allowing binder transactions to be matched to their corresponding
wake event.
"""


class PendingBinderTransaction:

    def __init__(self, event, pidtracer):
        self.parent_pid = event.dest_pid
        # if event.dest_pid in pidtracer.allBinderPIDStrings:
        if event.dest_pid in pidtracer.binder_pids:
            self.child_pids = event.dest_pid
        else:
            self.child_pids = pidtracer.find_child_binder_threads(event.dest_pid)
        self.send_event = event


class PendingBinderTask:

    def __init__(self, from_event, dest_event):
        self.from_pid = from_event.pid
        self.dest_pid = dest_event.dest_pid
        self.binder_thread = dest_event.pid
        self.time = from_event.time
        self.duration = dest_event.time - from_event.time


class ProcessTree:

    def __init__(self, pidtracer, metrics):

        self.metrics = metrics
        self.graph = nx.DiGraph()
        self.pidtracer = pidtracer

        self.process_branches = dict()
        self.pending_binder_transactions = []
        self.pending_binder_tasks = []

        self.cpus = []
        self.create_cpu_branches()
        self.gpu = GPUBranch(self.metrics.gpu_freq, self.metrics.gpu_util, self.graph)

        self.create_pid_branches()

    def create_cpu_branches(self):
        for x in range(0, self.metrics.core_count):
            self.cpus.append(CPUBranch(x, self.metrics.core_freqs[x],
                                       self.metrics.core_utils[x], self.graph))

    def create_pid_branches(self):
        for i, pid in self.pidtracer.app_pids.iteritems():
            self.process_branches[i] = ProcessBranch(pid.pid, pid.pname, pid.tname, None, self.graph,
                                                     self.pidtracer, self.cpus, self.gpu)
        for i, pid in self.pidtracer.system_pids.iteritems():
            self.process_branches[i] = ProcessBranch(pid.pid, pid.pname, pid.tname, None, self.graph,
                                                     self.pidtracer, self.cpus, self.gpu)
        for i, pid in self.pidtracer.binder_pids.iteritems():
            self.process_branches[i] = ProcessBranch(pid.pid, pid.pname, pid.tname, None, self.graph,
                                                     self.pidtracer, self.cpus, self.gpu)

    def finish_tree(self, finish_time, filename):
        with open(filename + "_results.csv", "w+") as f:
            writer = csv.writer(f, delimiter=',')

            # Start and end time
            start_time = 0
            end_time = 0
            for x, branch in self.process_branches.iteritems():
                if branch.tasks:
                    if branch.tasks[0].start_time < start_time or start_time == 0:
                        start_time = branch.tasks[0].start_time
                    if (branch.tasks[-1].start_time + branch.tasks[-1].duration) > end_time or end_time == 0:
                        end_time = branch.tasks[-1].start_time + branch.tasks[-1].duration

            writer.writerow(["Start", start_time / 1000000.0])
            writer.writerow(["Finish", end_time / 1000000.0])
            duration = (end_time - start_time) * 0.000001
            writer.writerow(["Duration", duration])

            writer.writerow([PL_PID, PL_PID_PNAME, PL_PID_TNAME, PL_TASK_COUNT,
                             PL_ENERGY, PL_DURATION])

            total_energy = 0

            # Calculate GPU energy
            gpu_energy = self.metrics.sys_util.gpu_utils.calc_GPU_power()
            writer.writerow(["GPU", gpu_energy])

            total_energy += gpu_energy

            for x in list(self.process_branches.keys()):
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
                writer.writerow([branch.pid, branch.pname, branch.tname, str(len(branch.tasks)),
                                 branch.energy, branch.duration])
            writer.writerow([])
            writer.writerow(["Total Energy", total_energy])
            try:
                writer.writerow(["Average wattage", total_energy / duration])
            except ZeroDivisionError:
                print "No events were recorded!"

            # Go through each branch and calculate the values energy values for each second
            energy_timeline = [0.0] * int(duration + 1)

            for x, branch in self.process_branches.iteritems():
                for i in range(len(energy_timeline)):
                    energy_timeline[i] += branch.get_second_energy(i, start_time)

            writer.writerow(["Sec", "Energy"])
            for x, second in enumerate(energy_timeline):
                writer.writerow([str(x), str(second)])

    def handle_event(self, event, subgraph, start_time, finish_time):

        # Ignore events that do not fall in the time window of interest
        if event.time < start_time or event.time > finish_time:
            return

        # Wakeup events show us the same information as sched switch events and
        # as such can be neglected when it comes to generating directed graphs
        if isinstance(event, EventWakeup):
            return

        # Sched switch events are the key events to track task activity.
        # They show us which process was slept and which was woken. Showing the
        # previous task's state
        elif isinstance(event, EventSchedSwitch):
            # start_time = time.time()

            # task being switched out
            if event.pid != 0:
                try:
                    process_branch = self.process_branches[event.pid]
                    process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_OUT, subgraph=subgraph)
                except KeyError:
                    pass

            # task being switched in
            if event.next_pid != 0:
                try:
                    process_branch = self.process_branches[event.next_pid]

                    binder_response = False
                    # if switched in because of binder
                    for x, task in enumerate(self.pending_binder_tasks):
                        if event.next_pid == task.dest_pid:
                            binder_response = True

                            # edge from prev task to binder thread
                            self.graph.add_edge(
                                # original process branch that started transaction
                                self.process_branches[task.from_pid].tasks[-1],
                                # this branch as it is being woken
                                self.process_branches[task.binder_thread].tasks[-1],
                                color='palevioletred3', dir='forward', style='bold')

                            process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_IN, subgraph=subgraph)

                            # edge from binder thread to next task
                            self.graph.add_edge(
                                # original process branch that started transaction
                                self.process_branches[task.binder_thread].tasks[-1],
                                # this branch as it is being woken
                                self.process_branches[task.dest_pid].tasks[-1],
                                color='yellow3', dir='forward')

                            # remove binder task that is now complete
                            del self.pending_binder_tasks[x]

                    if not binder_response:
                        process_branch.add_job(event, event_type=JobType.SCHED_SWITCH_IN, subgraph=subgraph)

                except KeyError:
                    pass

            # print ("Sched switch event processed in %s seconds" % (time.time() - start_time))

            return

        elif isinstance(event, EventFreqChange):
            for i in range(event.target_cpu, event.target_cpu + 4):
                self.metrics.core_freqs[i] = event.freq
                self.metrics.core_utils[i] = event.util
                self.cpus[i].add_job(event)
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

        elif isinstance(event, EventTempInfo):
            self.metrics.unprocessed_temps.append(TempLogEntry(event.time, event.big0, event.big1,
                                                               event.big2, event.big3, event.little, event.gpu))

        # Binder transactions show IPCs between tasks.
        # As a binder transaction represents the blocking of the client task
        # the transactions are processed as sleep events for the client tasks.
        # Binder transactions happen in two parts, they send to a binder thread
        # then the tread sends to the target task. As such binder transactions
        # are identified by if they send or recv from a binder thread then
        # handled accordingly
        elif isinstance(event, EventBinderCall):

            # From client process to binder thread
            if event.pid in self.pidtracer.app_pids or \
                    event.pid in self.pidtracer.system_pids:

                # TODO sometimes binder transactions are sent to binder threads without a target
                #  process. I am unsure what purpose this serves
                if event.dest_pid in self.pidtracer.binder_pids:
                    return

                # Push binder event on to pending list so that when the second
                # half of the transaction is performed the events can be merged.
                # The first half should give the event PID and time stamp
                # The second half gives to_proc PID and recv_time timestamp
                self.pending_binder_transactions.append( \
                    PendingBinderTransaction(event, self.pidtracer))

            # from binder thread to target server process
            elif event.pid in self.pidtracer.binder_pids:

                # get event from binder transactions list and merge
                if self.pending_binder_transactions:
                    process_branch = \
                        self.process_branches[event.pid]
                    for x, transaction in \
                            enumerate(self.pending_binder_transactions):

                        # If the binder thread that is completing the transaction
                        # is a child of a previous transactions parent binder PID
                        if any(pid == event.pid for pid in transaction.child_pids) or \
                                event.pid == transaction.parent_pid:
                            # Add starting binder event to branch
                            process_branch.add_job(transaction.send_event, event_type=JobType.BINDER_SEND)

                            # Add job to the branch of the Binder thread
                            process_branch.add_job(event, event_type=JobType.BINDER_RECV)

                            # add pending task
                            self.pending_binder_tasks.append \
                                (PendingBinderTask(transaction.send_event, event))

                            # remove completed transaction
                            del self.pending_binder_transactions[x]
