#!/usr/bin/env python

"""
Tracecmd trace events are wrapped into event objects that can then be handled to construct a task graph of the target
application.

Necessary trace events, such as sched_switch and binder_transaction events, are parsed from the tracecmd events
found in the tracecmd .dat file that is pulled from the target system after the trace has been performed.
These events are all derivatives of the event base class which gives the PID, CPU, name and time stamp of the event.
Interpolation between these events allows for binder transactions to be reconstructed as well as the IPC dependencies
between tasks being able to be co-ordinated with the sched_switch events that track when and where a task is running.
"""

import csv

import networkx as nx
from pydispatch import dispatcher

from SystemMetrics import *

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

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

    def __str__(self):
        return str(self.value)


class Event:
    """ All traced events for task graph extraction always provide the PID that is involved with the event,
    the timestamp of the event, the CPU on which the event occurred and the name of the event.
    """

    def __init__(self, pid, ts, cpu, name):
        self.pid = pid
        self.time = ts
        self.cpu = cpu
        self.name = name


class EventSchedSwitch(Event):
    """ Sched switch events are the swapping of two threads on a CPU. The event is tracked by the PIDs
    of the thread being swapped off and the one being swapped in. The state of the thread being swapped
    out is also provided. This is useful to check if a thread was finished executing and in a sleeping
    state when it was swapped off of the CPU.
    """

    def __init__(self, pid, ts, cpu, name, prev_state, next_pid, next_name):
        Event.__init__(self, pid, ts, cpu, name)
        self.prev_state = prev_state
        self.next_pid = next_pid
        self.next_name = next_name


class EventFreqChange(Event):
    """ The frequency of the systems' CPUs is changed when a cpu_freq event occurs
    """

    def __init__(self, pid, ts, cpu, freq, util, target_cpu):
        Event.__init__(self, pid, ts, cpu, "freq change")
        self.freq = freq
        self.util = util
        self.target_cpu = target_cpu


class EventWakeup(Event):

    def __init__(self, pid, ts, cpu, name):
        Event.__init__(self, pid, ts, cpu, name)


class EventIdle(Event):
    """ Idle events are used to track how long a certain CPU is no in use and therefore the utilization
    of a thread when executing.

    """

    def __init__(self, ts, cpu, name, state):
        Event.__init__(self, 0, ts, cpu, name)
        self.state = state


class EventBinderTransaction(Event):
    """ Binder transactions represent a half (first or second) of an IPC call between two threads.

    """

    def __init__(self, pid, ts, cpu, name, reply, dest_proc, target_pid, flags, code, tran_num):
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
        self.dest_proc = dest_proc
        self.target_pid = target_pid
        self.flags = flags
        self.code = code
        self.recv_time = 0
        self.transaction = tran_num


class EventMaliUtil(Event):
    """ Mali GPU metrics are found through the syslogger 'mali' events.

    """

    def __init__(self, pid, ts, cpu, util, freq):
        Event.__init__(self, pid, ts, cpu, "mali util")
        self.util = util
        self.freq = freq


class EventTempInfo(Event):
    """ INA sensor temperature values are tracked and stored during system runtime through the
    periodic 'exynos_temp' syslogger events.

    """

    def __init__(self, ts, cpu, big0, big1, big2, big3, gpu):
        Event.__init__(self, 0, ts, cpu, "temp")
        self.big0 = big0
        self.big1 = big1
        self.big2 = big2
        self.big3 = big3
        self.little = (big0 + big1 + big2 + big3) / 4.0
        self.gpu = gpu


class FreqPowerEvent:
    """ When calculating the power required for a task one needs to know the utilization
    and frequency. The utilization can be assumed to not vary a significant amount during
    the execution of a single job but the frequency should be tracked. A power chunk keeps
    track of the frequency levels used during a job as well as the durations such that the
    total duration of the job can later be divided into periods of different frequency
    use.

    The event stores a snapshot of the system's metrics at the time of the event, before the
    metrics are changed to their new values.
    """

    def __init__(self, ts, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util):
        self.time = ts
        self.cpu = cpu
        self.cpu_frequency = cpu_freq  # Frequency up until the event, not the frequency after the event
        self.gpu_frequency = gpu_freq
        self.cpu_util = cpu_util  # Not really needed
        self.gpu_util = gpu_util


class TaskNode:
    """
    A task represents a collection of jobs that have been executed between a
    wake event bringing the process out of sleep (S) until it returns to sleep from
    the running state (R)

    Because sched_switch events do not show the next state, the last event must be
    kept so that when another switch event giving prev_state=S is performed the last
    event is then known to be the sleep event and can then be processed accordingly.
    As such task processing must have a lead of one job.

    Calculating task cycles works on incremental summing. If the CPU on which the process is
    running or the GPU changes or the frequency changes then the variable is updated and
    the calc time shifted to the point of the event. As such the calc time stores the time since
    the exec time was last changed, and given that the CPU and frequency have been fixed during
    that time, the cycles is easily updated using a += and the current values (before updating them)
    """

    def __init__(self, graph, pid):
        self.events = []
        self.sys_metric_change_events = []
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

    def add_event(self, event, subgraph=False):
        """ Adds an event to the current task. Creation of new tasks is handled at a branch level. At a task
        level the addition of events handles the updating of metrics and the creation of sub-graphs.

        :param event: Event that is to be added to the task node. This event would also create a job node in
        the node's subgraph
        :param subgraph: Boolean value that enables the drawing of the task node's job nodes in a subgraph
        :return:
        """

        if not self.events:  # First event
            self.start_time = event.time

        # Switching events
        if isinstance(event, EventSchedSwitch):

            if event.pid == self.pid:  # Switching out
                if self.calc_time is 0:
                    self.calc_time = event.time

                if self.sys_metric_change_events:  # Handle event that will change energy consumption
                    for x, pe in enumerate(self.sys_metric_change_events):

                        if pe.time < self.events[-1].time:
                            continue
                        # calc time is the point until which the energy has been calculated
                        new_cycles = int((pe.time - self.calc_time) * 0.000000001 * pe.cpu_frequency)
                        self.util = SystemMetrics.current_metrics.sys_util_history.cpu[pe.cpu].get_util(pe.time)
                        self.temp = SystemMetrics.current_metrics.get_temp(pe.time, pe.cpu)

                        cycle_energy = self._get_cpu_per_second_energy(pe.cpu, pe.cpu_frequency, self.util,
                                                                       self.temp) / pe.cpu_frequency
                        self.cpu_cycles += new_cycles
                        self.energy += cycle_energy * new_cycles
                        self.duration += pe.time - self.calc_time
                        self.calc_time = pe.time

                    del self.sys_metric_change_events[:]  # Remove after processing

                if event.time != self.calc_time:  # Calculate remainder of energy consumption
                    cpu_speed = SystemMetrics.current_metrics.get_cpu_core_freq(event.cpu)

                    new_cycles = int((event.time - self.calc_time) * 0.000000001 * cpu_speed)
                    self.util = SystemMetrics.current_metrics.sys_util_history.cpu[event.cpu].get_util(event.time)
                    self.temp = SystemMetrics.current_metrics.get_temp(event.time, event.cpu)

                    cycle_energy = self._get_cpu_per_second_energy(event.cpu, cpu_speed, self.util,
                                                                   self.temp) / cpu_speed

                    self.cpu_cycles += new_cycles
                    self.energy += cycle_energy * new_cycles
                    self.duration += event.time - self.calc_time
                    self.calc_time = event.time

            if event.next_pid == self.pid:  # Switching in
                self.calc_time = event.time  # No energy has been summed yet

        self.events.append(event)  # Add event (job) to task

        if subgraph:
            if isinstance(event, EventSchedSwitch):
                self.graph.add_node(event,
                                    label=str(event.time)[:-6] + "." + str(event.time)[-6:]
                                    + " CPU: " + str(event.cpu) + "\n" + str(event.pid)
                                    + " ==> " + str(event.next_pid)
                                    + "\nPrev state: " + str(event.prev_state)
                                    + "\n" + event.name + " --> " + event.next_name + "\n"
                                    + str(event.__class__.__name__),
                                    fillcolor='bisque1', style='filled', shape='box')

            if len(self.events) >= 2:  # Inter-job edges
                self.graph.add_edge(self.events[-2], self.events[-1], color='violet', dir='forward')

    def finish(self):
        """ Set the time at which the task finished. The last event in a task will be the switch out event
        and as such this event's timestamp will be the end time of the current task.
        """
        self.finish_time = self.events[-1].time

    def add_cpu_gpu_event(self, ts, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util):
        """ When a frequency or utilization value (needed for energy calculations) changes during a task's
        execution a power event is added to a list that is then processed when the task ends. This allows
        for accurate calculation of energy values over the duration of the task as there is a recorded history
        of the system's metrics and changes over the duration of the task.

        :param ts: Time at which the event happened
        :param cpu:
        :param cpu_freq:
        :param cpu_util:
        :param gpu_freq:
        :param gpu_util:
        :return:
        """
        self.sys_metric_change_events.append(FreqPowerEvent(ts, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util))

    @staticmethod
    def _get_cpu_per_second_energy(cpu, freq, util, temp):
        """ Using the values calculated for the energy profile of the Odroid XU3, using a regression model,
        the per-second energy consumption (in joules) can be calculated using the found values and the
        formula:
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)

        :param cpu: CPU core index of the target CPU core. 0-3 are LITTLE cores and 4-7 are big cores.
        :param freq: The frequency of the target CPU core
        :param util: The utilization of the target CPU core
        :param temp: The temperature of the target CPU core
        :return: Per-second energy consumption of the target core (in joules)
        """
        try:
            energy_profile = SystemMetrics.current_metrics.energy_profile
            if cpu in range(4):
                try:
                    voltage = energy_profile.little_voltages[freq]
                except IndexError:
                    print "Couldn't get voltage for little core at freq: %d" % freq
                    sys.exit(-1)
                a1 = energy_profile.little_reg_const["a1"]
                a2 = energy_profile.little_reg_const["a2"]
                a3 = energy_profile.little_reg_const["a3"]
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
                return energy
            else:
                try:
                    voltage = energy_profile.big_voltages[freq]
                except IndexError:
                    print "Couldn't get voltage for big core at freq: %d" % freq
                    sys.exit(-1)
                a1 = energy_profile.big_reg_const["a1"]
                a2 = energy_profile.big_reg_const["a2"]
                a3 = energy_profile.big_reg_const["a3"]
                energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
                return energy
        except ValueError:
            print "Invalid frequency"
        except TypeError:
            print "Type error"


class BinderNode(TaskNode):

    def __init__(self, graph, pid):
        TaskNode.__init__(self, graph, pid)


class CPUBranch:
    """ Each core of the system has a CPUBranch which stores the previous and current metrics for the core,
    retaining to frequency values and utilization.

    """

    def __init__(self, cpu_number, initial_freq, initial_util, graph):
        self.cpu_num = cpu_number
        self.freq = initial_freq
        self.prev_freq = initial_freq
        self.util = initial_util
        self.prev_util = initial_util
        self.events = []
        self.graph = graph
        self.signal_freq = "freq_change" + str(self.cpu_num)

    def add_event(self, event):
        """ Adds an event to the stored history of the CPU branch. Also checks if the added event updates the
        actual metrics of the CPU.

        :param event: Event to be added to the CPU branch's history
        """

        self.events.append(event)

        if event.freq != self.freq or event.util != self.util:  # Update current metrics
            self.prev_freq = self.freq
            self.freq = event.freq

            if self.util is 0:
                self.prev_util = event.util
            else:
                self.prev_util = self.util
            self.util = event.util

            self._send_change_event()

    def _send_change_event(self):
        dispatcher.send(signal=self.signal_freq, sender=dispatcher.Any)


class GPUBranch:
    """
    The GPU branch stores a chronological history of all events that relate to the
    GPU's metrics
    """

    def __init__(self, initial_freq, initial_util, graph):
        self.freq = initial_freq
        self.prev_freq = initial_freq
        self.util = initial_util
        self.prev_util = initial_util
        self.graph = graph
        self.events = []
        self.signal_change = "gpu_change"  # Dispatcher signal

    def _send_change_event(self):
        """
        Send the signal to all dispatcher listeners that the GPU has changed it stats
        """
        dispatcher.send(signal=self.signal_change, sender=dispatcher.Any)

    def add_event(self, event):
        """
        :param event: A EventMaliUtil to be added to the GPU branch
        """
        self.events.append(event)

        if event.freq != self.freq or event.util != self.util:  # Update current metrics
            self.prev_freq = self.freq
            self.freq = event.freq

            if self.util is 0:
                self.prev_util = event.util
            else:
                self.prev_util = self.util
            self.util = event.util


class EnergyDuration:
    """
    A class to return energy sums from tasks
    """

    def __init__(self):
        self.energy = 0
        self.duration = 0


class ProcessBranch:
    """
    Events must be added to the "branch" of their PID. The branch consists of tasks,
    each task being comprised of jobs/slices (time spend executing thread between a wake and
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
        self.energy = 0  # calculated upon request at the end between given intervals
        self.duration = 0

    def _connect_to_cpu_event(self, cpu):
        """ Threads can change the CPU on which they are scheduled, to handle changes in PID->CPU allocation
        each active PID task subscribes to a certain CPU branch from which it receives changes in the CPU's
        metrics, needed for accurate energy calculation.

        :param cpu: CPU index to which the PID branch wishes to subscribe
        """
        try:
            dispatcher.connect(self._handle_cpu_freq_change, signal=self.cpus[cpu].signal_freq,
                               sender=dispatcher.Any)
        except IndexError:
            print "CPUs not init'd"
            sys.exit(1)

    def _disconnect_from_cpu_event(self, cpu):
        """ Disconnects a PID branch from a certain CPU's metric update signal

        :param cpu: CPU index from which the PID branch should be unsubscribed
        """
        try:
            dispatcher.disconnect(self._handle_cpu_freq_change, signal=self.cpus[cpu].signal_freq,
                                  sender=dispatcher.Any)
        except IndexError:
            print "IndexError in disconnecting from cpu"
            sys.exit(1)

    def _handle_cpu_freq_change(self):
        """ Adds a CPU/GPU metric change event to the current branch. This event snapshots the CPU's metrics
        before they were changed. The GPU's metrics have not changed and as such the current ones can be used.

        """
        if self.tasks:
            try:
                self.tasks[-1].add_cpu_gpu_event(self.cpus[self.cpu].events[-1].time,
                                                 self.cpu,
                                                 self.cpus[self.cpu].prev_freq,
                                                 self.cpus[self.cpu].prev_util,
                                                 self.gpu.freq,
                                                 self.gpu.util)
            except IndexError:
                print "IndexError in handling CPU freq change"
                sys.exit(1)

    def _handle_cpu_num_change(self, event):
        """ Adds a CPU/GPU metric change event to the current branch. This event snapshots the CPU's metrics
        before the CPU was changed. If the new CPU has a different frequency to the previous one then a change
        event is created. The GPU's metrics have not changed and as such the current ones can be used.

        """
        if self.tasks:
            try:
                if self.cpus[event.cpu].freq != self.cpus[self.cpu].freq:
                    self.tasks[-1].add_cpu_gpu_event(event.time,
                                                     self.cpu,
                                                     self.cpus[self.cpu].freq,
                                                     self.cpus[self.cpu].util,
                                                     self.gpu.freq,
                                                     self.gpu.util)
            except IndexError:
                print "IndexError in handing CPU num change"
                sys.exit(1)

        self._disconnect_from_cpu_event(self.cpu)
        self.cpu = event.cpu
        self._connect_to_cpu_event(self.cpu)

    def get_second_energy(self, second, start_time, finish_time):
        """ Returns the energy consumed by a process during a given second offset from an initial start time,
        constrained by a finish time.

        :param second: The number of seconds that the time window of interest is offset from the start time
        :param start_time: The time at which the energy calculations are offset from
        :param finish_time: An upper bound which cannot be exceeded.
        :return: The calculated energy (in joules) for the specified second
        """
        nanosecond_start = start_time + (second * 1000000)
        nanosecond_finish = nanosecond_start + 1000000
        if finish_time < nanosecond_finish:
            nanosecond_finish = finish_time

        return self.get_task_energy(nanosecond_start, nanosecond_finish).energy

    def get_task_energy(self, start_time, finish_time):
        """ Sums the energy of the task between two time bounds

        :param start_time: The time at which energy consumption should start being summed
        :param finish_time: The time at which energy consumption should stop being summed
        :return: The energy sum and precise time over which the energy value was summed
        """
        tasks_stats = EnergyDuration()

        for task in self.tasks:
            # Task that falls at starting point
            if (task.start_time < start_time) and (task.finish_time > start_time):
                try:
                    tasks_stats.energy += ((task.finish_time - start_time) / task.duration * task.energy)
                    tasks_stats.duration += (task.finish_time - start_time)
                except ZeroDivisionError:
                    continue
            # Task that falls at the ending of the second
            elif (task.start_time <= finish_time) and (task.finish_time > finish_time):
                try:
                    tasks_stats.energy += ((finish_time - task.start_time) / task.duration * task.energy)
                    tasks_stats.duration += (finish_time - task.start_time)
                except ZeroDivisionError:
                    continue
            # Middle events
            elif (task.start_time >= start_time) and (task.finish_time <= finish_time):
                tasks_stats.energy += task.energy
                tasks_stats.duration += task.duration
            # Finished second
            elif task.start_time >= finish_time:
                return tasks_stats

        return tasks_stats

    def add_event(self, event, event_type=JobType.UNKNOWN, subgraph=False):
        """ Handles the adding of events to the branch, specifically making sure that there is an active task
        to which the event can be added and that the event is connected to the correct CPU.

        :param event: Event that is to be added to the PID branch
        :param event_type: A more detailed enum describing the type of event. Used to distinguish, for example,
        the first and second halves of a binder transaction
        :param subgraph: Boolean that is used to toggle the drawing of task nodes' sub-graphs
        """

        if self.cpu is None:  # CPU association
            self.cpu = event.cpu
            self._connect_to_cpu_event(self.cpu)

        if event_type == JobType.SCHED_SWITCH_OUT:

            if not self.tasks:
                self.tasks.append(TaskNode(self.graph, self.pid))
                self.tasks[-1].add_event(event, subgraph=subgraph)

                if event.prev_state == str(ThreadState.INTERRUPTIBLE_SLEEP_S):
                    self.active = False
                    self.tasks[-1].finish()
                return

            elif event.prev_state == str(ThreadState.INTERRUPTIBLE_SLEEP_S) and \
                    event.pid not in self.pidtracer.binder_pids:

                self.tasks[-1].add_event(event, subgraph=subgraph)
                self.tasks[-1].finish()

                self.active = False  # Current task has ended and new one will be needed

                self.graph.add_node(self.tasks[-1],
                                    label=str(self.tasks[-1].start_time)[:-6] + "."
                                    + str(self.tasks[-1].start_time)[-6:]
                                    + " ==> " + str(self.tasks[-1].finish_time)[:-6] + "."
                                    + str(self.tasks[-1].finish_time)[-6:]
                                    + "\nCPU: " + str(event.cpu)
                                    + "   Util: " + str(self.tasks[-1].util) + "%"
                                    + "   Temp: " + str(self.tasks[-1].temp)
                                    + "   PID: " + str(event.pid)
                                    + "\nGPU: " + str(SystemMetrics.current_metrics.current_gpu_freq) + "Hz   "
                                    + str(SystemMetrics.current_metrics.current_gpu_util) + "% Util"
                                    + "\nDuration: " + str(self.tasks[-1].duration)
                                    + "\nCPU Cycles: " + str(self.tasks[-1].cpu_cycles)
                                    + "\nEnergy: " + str(self.tasks[-1].energy)
                                    + "\n" + str(event.name)
                                    + "\n" + str(self.tasks[-1].__class__.__name__),
                                    fillcolor='darkolivegreen3',
                                    style='filled,bold,rounded', shape='box')

                if subgraph:
                    self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[0], color='blue',
                                        dir='forward')
                    self.graph.add_edge(self.tasks[-1], self.tasks[-1].events[-1], color='red',
                                        dir='back')
                return

        elif event_type == JobType.SCHED_SWITCH_IN:

            if event.cpu != self.cpu:  # If the CPU has changed
                self._handle_cpu_num_change(event)

            if self.active is False:  # New task starting

                self.tasks.append(TaskNode(self.graph, self.pid))
                self.tasks[-1].add_event(event, subgraph=subgraph)
                self.active = True

                if len(self.tasks) >= 2:  # Connecting task in the same PID branch for visual aid
                    self.graph.add_edge(self.tasks[-2], self.tasks[-1], color='lightseagreen',
                                        style='dashed')
                return

        elif event_type == JobType.BINDER_SEND:
            self.tasks.append(BinderNode(self.graph, self.pid))
            self.tasks[-1].add_event(event, subgraph=subgraph)
            return

        elif event_type == JobType.BINDER_RECV:

            self.tasks[-1].add_event(event, subgraph=subgraph)
            self.tasks[-1].finish()

            self.graph.add_node(self.tasks[-1],
                                label=str(self.tasks[-1].events[0].time)[:-6]
                                + "." + str(self.tasks[-1].events[0].time)[-6:]
                                + " ==> " + str(self.tasks[-1].events[-1].time)[:-6]
                                + "." + str(self.tasks[-1].events[-1].time)[-6:]
                                + "\nPID: " + str(event.pid)
                                + "  dest PID: " + str(event.target_pid)
                                + "\nType: " + str(self.tasks[-1].events[0].trans_type.name)
                                + "\n" + str(event.name)
                                + "\n" + str(self.tasks[-1].__class__.__name__),
                                fillcolor='coral', style='filled,bold', shape='box')
            return

        else:  # All other job types just need to get added to the task
            self.tasks[-1].add_event(event, subgraph=subgraph)


class FirstHalfBinderTransaction:
    """ Binder transactions are often directed to the parent binder thread of a
    system service. The exact PID of the child binder thread that will perform the
    transaction is not known when the first half of the transaction is completed.
    A list of child binder threads is found for the parent binder thread.
    This list is used to match the second half of the binder transaction to any
    pending first halves.
    """

    def __init__(self, event, parent_pid, pidtracer):
        self.parent_pid = parent_pid
        self.child_pids = pidtracer.find_child_binder_threads(parent_pid)
        self.send_event = event


class CompletedBinderTransaction:
    """ A binder transaction is completed in two halves, firstly a transaction is performed to a target
    binder process. This binder process allocates the second half of the transaction to one of its
    child threads.
    """

    def __init__(self, first_half_event, second_half_event):
        self.caller_pid = first_half_event.pid
        self.target_pid = second_half_event.target_pid
        self.binder_thread = second_half_event.pid
        self.time = first_half_event.time
        self.duration = second_half_event.time - first_half_event.time
        self.first_half = first_half_event
        self.second_half = second_half_event


class ProcessTree:
    """ A tree of PID branches that represents all of the PIDs that are relevant to the target application
    """

    def __init__(self, pidtracer, metrics):

        self.metrics = metrics
        self.graph = nx.DiGraph()
        self.pidtracer = pidtracer

        self.process_branches = dict()
        self.pending_binder_calls = []
        self.completed_binder_calls = []
        self.cpus = []

        self._create_cpu_branches()
        self.gpu = GPUBranch(self.metrics.current_gpu_freq, self.metrics.current_gpu_util, self.graph)
        self._create_pid_branches()

    def _create_cpu_branches(self):
        """ Creates a CPU branch for each CPU found in a system
        """
        for x in range(0, self.metrics.core_count):
            self.cpus.append(CPUBranch(x, self.metrics.current_core_freqs[x],
                                       self.metrics.current_core_utils[x], self.graph))

    def _create_pid_branches(self):
        """ Each PID in the tree creates a branch on which jobs and tasks of that PID are created in a
        chronological order such that the branch is a directed (in time) execution history of the
        branch's PID.
        """
        for i, pid in self.pidtracer.app_pids.iteritems():
            self.process_branches[i] = ProcessBranch(pid.pid, pid.pname, pid.tname, None, self.graph,
                                                     self.pidtracer, self.cpus, self.gpu)
        for i, pid in self.pidtracer.system_pids.iteritems():
            self.process_branches[i] = ProcessBranch(pid.pid, pid.pname, pid.tname, None, self.graph,
                                                     self.pidtracer, self.cpus, self.gpu)
        for i, pid in self.pidtracer.binder_pids.iteritems():
            self.process_branches[i] = ProcessBranch(pid.pid, pid.pname, pid.tname, None, self.graph,
                                                     self.pidtracer, self.cpus, self.gpu)

    def finish_tree(self, filename):
        """ After all events have been added to a tree the tree compiles its energy results and
        writes them to a CSV file. Summaries of each PID's energy consumption as well as total
        tree energy metrics are provided.

        :param filename: Filename prefix which is used to differentiate the current trace
        """
        with open(filename + "_results.csv", "w+") as f:
            writer = csv.writer(f, delimiter=',')

            # Start and end time
            start_time = 0
            finish_time = 0
            for x, branch in self.process_branches.iteritems():
                if branch.tasks:
                    if branch.tasks[0].start_time < start_time or start_time == 0:
                        start_time = branch.tasks[0].start_time
                    if (branch.tasks[-1].start_time + branch.tasks[-1].duration) > finish_time or finish_time == 0:
                        finish_time = branch.tasks[-1].start_time + branch.tasks[-1].duration

            writer.writerow(["Start", start_time / 1000000.0])
            writer.writerow(["Finish", finish_time / 1000000.0])
            duration = (finish_time - start_time) * 0.000001
            writer.writerow(["Duration", duration])

            writer.writerow([PL_PID, PL_PID_PNAME, PL_PID_TNAME, PL_TASK_COUNT,
                             PL_ENERGY, PL_DURATION])

            total_energy = 0

            # Calculate GPU energy
            gpu_energy = self.metrics.sys_util_history.gpu.get_energy(start_time, finish_time)
            writer.writerow(["GPU", gpu_energy])

            total_energy += gpu_energy

            for x in list(self.process_branches.keys()):
                branch = self.process_branches[x]
                # Remove empty PID branches
                if len(branch.tasks) == 0:
                    del self.process_branches[x]
                    continue
                branch_stats = branch.get_task_energy(start_time, finish_time)
                branch.energy = branch_stats.energy
                total_energy += branch.energy
                branch.duration = branch_stats.duration

                if branch.energy == 0.0:
                    continue

                # Write results to file
                writer.writerow([branch.pid, branch.pname, branch.tname, str(len(branch.tasks)),
                                 branch.energy, branch.duration])
            writer.writerow([])
            writer.writerow(["Total Energy", total_energy])
            try:
                writer.writerow(["Average wattage", total_energy / duration])
            except ZeroDivisionError:
                print "No events were recorded!"

            writer.writerow([])
            writer.writerow(["Energy Timeline"])

            # Go through each branch and calculate the values energy values for each second
            energy_timeline = [[0.0, 0.0] for _ in range(int(duration + 1))]

            for x, branch in self.process_branches.iteritems():
                for i, second in enumerate(energy_timeline):
                    energy = branch.get_second_energy(i, start_time, finish_time)
                    second[0] += energy

            for i, second in enumerate(energy_timeline):
                second[1] += \
                    self.metrics.sys_util_history.gpu.get_second_energy(i, start_time, finish_time)

            writer.writerow(["Sec", "Thread Energy", "GPU Energy", "Total Energy"])
            for x, second in enumerate(energy_timeline):
                writer.writerow([str(x), str(second[0]), str(second[1]), str(second[0] + second[1])])

    def handle_event(self, event, subgraph, start_time, finish_time):
        """
        An event is handled by and added to the current trace tree, handled depending on event type.

        :param event: The event to be added into the tree
        :param subgraph: Boolean to enable to drawing of the task graph's node's sub-graphs
        :param start_time: Time after which events must happens if they are to be processed
        :param finish_time: Time before which events must happens if they are to be processed
        """

        if event.time < start_time or event.time > finish_time:  # Event time window
            return 1

        elif isinstance(event, EventSchedSwitch):  # PID context swap

            # Task being switched out, ignoring idle task and binder threads
            if event.pid != 0 and event.pid not in self.pidtracer.binder_pids:
                try:
                    process_branch = self.process_branches[event.pid]
                    process_branch.add_event(event, event_type=JobType.SCHED_SWITCH_OUT, subgraph=subgraph)
                except KeyError:
                    pass  # PID not of interest to program

            # Task being switched in, again ignoring idle task and binder threads
            if event.next_pid != 0 and event.next_pid not in self.pidtracer.binder_pids:
                try:
                    for x, pending_binder_node in reversed(list(enumerate(self.completed_binder_calls))):  # Most recent
                        # If the event being switched in matches the binder node's target
                        if event.next_pid == pending_binder_node.target_pid:
                            # Add first half binder event to binder branch
                            self.process_branches[pending_binder_node.binder_thread].add_event(
                                pending_binder_node.first_half, event_type=JobType.BINDER_SEND)

                            # Add second half binder event to binder branch
                            self.process_branches[pending_binder_node.binder_thread].add_event(
                                pending_binder_node.second_half, event_type=JobType.BINDER_RECV)

                            self.graph.add_edge(  # Edge from calling task to binder node
                                self.process_branches[pending_binder_node.caller_pid].tasks[-1],
                                self.process_branches[pending_binder_node.binder_thread].tasks[-1],
                                color='palevioletred3', dir='forward', style='bold')

                            # Switch in new pid which will find pending completed binder transaction and create a
                            # new task node
                            self.process_branches[event.next_pid].add_event(
                                event, event_type=JobType.SCHED_SWITCH_IN, subgraph=subgraph)

                            self.graph.add_edge(  # Edge from binder node to next task
                                self.process_branches[pending_binder_node.binder_thread].tasks[-1],
                                self.process_branches[pending_binder_node.target_pid].tasks[-1],
                                color='yellow3', dir='forward')

                            # remove binder task that is now complete
                            del self.completed_binder_calls[x]
                            return 0

                    self.process_branches[event.next_pid].add_event(
                        event, event_type=JobType.SCHED_SWITCH_IN, subgraph=subgraph)
                except KeyError:
                    pass
            return 0

        elif isinstance(event, EventBinderTransaction):

            if event.pid in self.pidtracer.app_pids:

                # First half of a binder transaction
                self.pending_binder_calls.append(
                    FirstHalfBinderTransaction(event, event.target_pid, self.pidtracer))
                return 0

            elif event.pid in self.pidtracer.system_pids:
                self.pending_binder_calls.append(
                    FirstHalfBinderTransaction(event, event.target_pid, self.pidtracer))

                caller_children = self.pidtracer.find_child_binder_threads(event.pid)
                self.pending_binder_calls[-1].child_pids += caller_children
                return 0

            elif event.pid in self.pidtracer.binder_pids:  # From binder process

                if self.pending_binder_calls:  # Pending first halves
                    # Find most recent first half
                    for x, transaction in reversed(list(enumerate(self.pending_binder_calls))):

                        if any(pid == event.pid for pid in transaction.child_pids) or \
                                event.pid == transaction.parent_pid:  # Find corresponding first half

                            self.completed_binder_calls.append(
                                CompletedBinderTransaction(transaction.send_event, event))

                            del self.pending_binder_calls[x]  # Remove completed first half
                            return 0
                return 0

        elif isinstance(event, EventFreqChange):
            for i in range(event.target_cpu, event.target_cpu + 4):
                self.metrics.current_core_freqs[i] = event.freq
                self.metrics.current_core_utils[i] = event.util
                self.cpus[i].add_event(event)
            return 0

        elif isinstance(event, EventMaliUtil):

            self.metrics.current_gpu_freq = event.freq
            self.metrics.current_gpu_util = event.util

            self.metrics.sys_util_history.gpu.add_event(event)

            self.gpu.add_event(event)

        elif isinstance(event, EventIdle):
            self.metrics.sys_util_history.cpu[event.cpu].add_idle_event(event)
            return 0

        elif isinstance(event, EventTempInfo):
            if self.metrics.sys_temps.initial_time == 0:
                self.metrics.sys_temps.initial_time = event.time
            self.metrics.sys_temps.end_time = self.metrics.sys_temps.end_time = event.time

            if len(self.metrics.sys_temps.temps) >= 1:
                for t in range(self.metrics.sys_temps.temps[-1].time - self.metrics.sys_temps.initial_time,
                               event.time - self.metrics.sys_temps.initial_time):
                    self.metrics.sys_temps.temps.append(TempLogEntry(event.time, event.big0, event.big1,
                                                                     event.big2, event.big3, event.little, event.gpu))
            else:
                self.metrics.sys_temps.temps.append(TempLogEntry(event.time, event.big0, event.big1,
                                                                 event.big2, event.big3, event.little, event.gpu))

        # Wakeup events show us the same information as sched switch events and
        # as such can be neglected when it comes to generating directed graphs
        if isinstance(event, EventWakeup):
            return 0
