#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

from SystemMetrics import SystemMetrics
from Dependencies import Dependency
from Optimizations import OptimizationInfo
from SystemEvents import EventSchedSwitch, FreqPowerEvent
from XU3EnergyProfile import XU3RegressionModel


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

    def __init__(self, graph, pid, name):

        self.events = []
        self.sys_metric_change_events = []
        self.cpu_cycles = 0
        self.gpu_cycles = 0
        self.start_time = 0
        self.calc_time = 0
        self.energy = [0.0, 0.0]
        self.duration = 0
        self.finish_time = 0
        self.graph = graph
        self.pid = pid
        self.name = name
        self.temp = 0
        self.util = 0
        self.dependency = Dependency()
        self.optimization_info = OptimizationInfo(graph)

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
                        new_cycles = int((pe.time - self.calc_time) * 0.000001 * pe.cpu_frequency)

                        self.util = [SystemMetrics.current_metrics.sys_util_history.cpu[(pe.cpu / 4) * 4 + 0].get_util(
                                pe.time)]
                        self.util.append(
                                SystemMetrics.current_metrics.sys_util_history.cpu[(pe.cpu / 4) * 4 + 1].get_util(
                                        pe.time))
                        self.util.append(
                                SystemMetrics.current_metrics.sys_util_history.cpu[(pe.cpu / 4) * 4 + 2].get_util(
                                        pe.time))
                        self.util.append(
                                SystemMetrics.current_metrics.sys_util_history.cpu[(pe.cpu / 4) * 4 + 3].get_util(
                                        pe.time))

                        self.temp = [SystemMetrics.current_metrics.get_temp(pe.time, (pe.cpu / 4) * 4 + 0)]
                        self.temp.append(SystemMetrics.current_metrics.get_temp(pe.time, (pe.cpu / 4) * 4 + 1))
                        self.temp.append(SystemMetrics.current_metrics.get_temp(pe.time, (pe.cpu / 4) * 4 + 2))
                        self.temp.append(SystemMetrics.current_metrics.get_temp(pe.time, (pe.cpu / 4) * 4 + 3))

                        cycle_energy = XU3RegressionModel.get_cpu_per_second_energy(pe.cpu, pe.cpu_frequency, self.util,
                                                                                    self.temp)
                        cycle_energy = [component / pe.cpu_frequency for component in cycle_energy]

                        self.cpu_cycles += new_cycles
                        new_energy = [component * new_cycles for component in cycle_energy]
                        new_summed_energy = [self.energy[i] + new_energy[i] for i in range(len(new_energy))]
                        self.energy = new_summed_energy
                        self.duration += pe.time - self.calc_time
                        self.calc_time = pe.time

                    del self.sys_metric_change_events[:]  # Remove after processing

                if event.time != self.calc_time:  # Calculate remainder of energy consumption

                    cpu_speed = SystemMetrics.current_metrics.get_cpu_core_freq(event.cpu)
                    new_cycles = int((event.time - self.calc_time) * 0.000001 * cpu_speed)

                    self.util = [SystemMetrics.current_metrics.sys_util_history.cpu[(event.cpu / 4) * 4 + 0].get_util(
                            event.time)]
                    self.util.append(
                            SystemMetrics.current_metrics.sys_util_history.cpu[(event.cpu / 4) * 4 + 1].get_util(
                                    event.time))
                    self.util.append(
                            SystemMetrics.current_metrics.sys_util_history.cpu[(event.cpu / 4) * 4 + 2].get_util(
                                    event.time))
                    self.util.append(
                            SystemMetrics.current_metrics.sys_util_history.cpu[(event.cpu / 4) * 4 + 3].get_util(
                                    event.time))

                    self.temp = [SystemMetrics.current_metrics.get_temp(event.time, (event.cpu / 4) * 4 + 0)]
                    self.temp.append(SystemMetrics.current_metrics.get_temp(event.time, (event.cpu / 4) * 4 + 1))
                    self.temp.append(SystemMetrics.current_metrics.get_temp(event.time, (event.cpu / 4) * 4 + 2))
                    self.temp.append(SystemMetrics.current_metrics.get_temp(event.time, (event.cpu / 4) * 4 + 3))

                    cycle_energy = XU3RegressionModel.get_cpu_per_second_energy(event.cpu, cpu_speed, self.util,
                                                                                self.temp)
                    cycle_energy = [component / cpu_speed for component in cycle_energy]

                    self.cpu_cycles += new_cycles
                    new_energy = [component * new_cycles for component in cycle_energy]
                    new_summed_energy = [self.energy[i] + new_energy[i] for i in range(len(new_energy))]
                    self.energy = new_summed_energy
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


class BinderNode(TaskNode):

    def __init__(self, graph, pid, name):
        TaskNode.__init__(self, graph, pid, name)
