#!/usr/bin/env python

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

import sys

from pydispatch import dispatcher
import numpy as np
from Dependencies import DependencyType
from Nodes import *
from SystemEvents import JobType, ThreadState


class EnergyDuration:
    """
    A class to return energy sums from tasks
    """
    def __init__(self):
        self.energy = [0.0, 0.0]
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
        self.binder_tasks = []
        self.start = start
        self.active = False
        self.graph = graph
        self.pidtracer = pidtracer
        self.cpu = None
        self.cpus = cpus
        self.gpu = gpu
        self.energy = [
            0.0,
            0.0,
        ]  # calculated upon request at the end between given intervals
        self.duration = 0

    def _connect_to_cpu_event(self, cpu):
        """ Threads can change the CPU on which they are scheduled, to handle changes in PID->CPU allocation
        each active PID task subscribes to a certain CPU branch from which it receives changes in the CPU's
        metrics, needed for accurate energy calculation.

        :param cpu: CPU index to which the PID branch wishes to subscribe
        """
        try:
            dispatcher.connect(
                self._handle_cpu_freq_change,
                signal=self.cpus[cpu].signal_freq,
                sender=dispatcher.Any,
            )
        except IndexError:
            print "CPUs not init'd"
            sys.exit(1)

    def _disconnect_from_cpu_event(self, cpu):
        """ Disconnects a PID branch from a certain CPU's metric update signal

        :param cpu: CPU index from which the PID branch should be unsubscribed
        """
        try:
            dispatcher.disconnect(
                self._handle_cpu_freq_change,
                signal=self.cpus[cpu].signal_freq,
                sender=dispatcher.Any,
            )
        except IndexError:
            print "IndexError in disconnecting from cpu"
            sys.exit(1)

    def _handle_cpu_freq_change(self):
        """ Adds a CPU/GPU metric change event to the current branch. This event snapshots the CPU's metrics
        before they were changed. The GPU's metrics have not changed and as such the current ones can be used.

        """
        if self.tasks:

            try:
                self.tasks[-1].add_cpu_gpu_event(
                    self.cpus[self.cpu].events[-1].time,
                    self.cpu,
                    self.cpus[self.cpu].prev_freq,
                    self.cpus[self.cpu].prev_util,
                    self.gpu.freq,
                    self.gpu.util,
                )
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
                    self.tasks[-1].add_cpu_gpu_event(
                        event.time,
                        self.cpu,
                        self.cpus[self.cpu].freq,
                        self.cpus[self.cpu].util,
                        self.gpu.freq,
                        self.gpu.util,
                    )
            except IndexError:
                print "IndexError in handing CPU num change"
                sys.exit(1)

        self._disconnect_from_cpu_event(self.cpu)
        self.cpu = event.cpu
        self._connect_to_cpu_event(self.cpu)

    def get_interval_energy(self, second, interval, start_time, finish_time):
        """ Returns the energy consumed by a process during a given second offset from an initial start time,
        constrained by a finish time.

        :param second: The number of intervals that the time window of interest is offset from the start time
        :param interval: The size of the time intervals that are being calculated
        :param start_time: The time at which the energy calculations are offset from
        :param finish_time: An upper bound which cannot be exceeded.
        :return: The calculated energy (in joules) for the specified second
        """
        nanosecond_start = start_time + (second * interval * 1000000)
        nanosecond_finish = nanosecond_start + interval * 1000000

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
            if (task.start_time < start_time) and (task.finish_time >
                                                   start_time):

                try:
                    energy_delta = [((task.finish_time - start_time) /
                                     task.duration * component)
                                    for component in task.energy]
                    for i in range(len(tasks_stats.energy)):
                        tasks_stats.energy[i] += energy_delta[i]

                    tasks_stats.duration += task.finish_time - start_time

                except ZeroDivisionError:
                    continue
            # Task that falls at the ending of the second
            elif (task.start_time <= finish_time) and (task.finish_time >
                                                       finish_time):

                try:
                    energy_delta = [((finish_time - task.start_time) /
                                     task.duration * component)
                                    for component in task.energy]
                    for i in range(len(tasks_stats.energy)):
                        tasks_stats.energy[i] += energy_delta[i]

                    tasks_stats.duration += finish_time - task.start_time

                except ZeroDivisionError:
                    continue
            # Middle events
            elif (task.start_time >= start_time) and (task.finish_time <=
                                                      finish_time):

                for i in range(len(tasks_stats.energy)):
                    tasks_stats.energy[i] += task.energy[i]

                tasks_stats.duration += task.duration
            # Finished second
            elif task.start_time >= finish_time:

                return tasks_stats

        return tasks_stats

    def get_optimization_timeline(self, start_us, interval_count, interval_us):
        finish_time = start_us + (interval_count * interval_us)
        # [DVFS,Task realloc]
        optimizations_timeline = np.full(interval_count * 2,
                                         [0]).reshape(interval_count, 2)

        for task in self.tasks:
            if (start_us < task.start_time
                    and task.start_time + task.duration <= finish_time):
                index = int(round((task.start_time - start_us) / interval_us))
                if task.optimization_info.dvfs_possible():
                    optimizations_timeline[index][1] += 1
                if task.optimization_info.realloc_possible():
                    optimizations_timeline[index][0] += 1

        return optimizations_timeline

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

                self.tasks.append(TaskNode(self.graph, self.pid, self.tname))
                self.tasks[-1].add_event(event, subgraph=subgraph)

                if event.prev_state == str(ThreadState.INTERRUPTIBLE_SLEEP_S):
                    self.active = False
                    self.tasks[-1].finish()
                else:
                    self.active = True

                return

            else:

                if event.prev_state == str(ThreadState.INTERRUPTIBLE_SLEEP_S):

                    self.active = (
                        False  # Current task has ended and new one will be needed
                    )

                    toi = self.tasks[-1]
                    toi.add_event(event, subgraph=subgraph)  ##
                    toi.finish()
                    utils_g = ("{}% ".format(round(k[1], 2))
                               for k in enumerate(toi.util))
                    utils = ""
                    for entry in utils_g:
                        utils += str(entry)
                    label = (
                        "{}.{} ==> {}.{}\nPID: {}\nCPU: {} @ {} Hz\nUtil: {}\nTemp: {}\nGPU: {}Hz Util {}% "
                        "\n Duration: {} CPU Cycles: {}\nEnergy: {};{}\n Dependency: {} Dependent: #{} "
                        "\nProc: '{}'\nThread: '{}'\nNode Type: {} ID: #{}".
                        format(
                            str(toi.start_time)[:-6],
                            str(toi.start_time)[-6:],
                            str(toi.finish_time)[:-6],
                            str(toi.finish_time)[-6:],
                            event.pid,
                            event.cpu,
                            event.cpu_freq[0 if event.cpu < 4 else 1],
                            utils,
                            toi.temp,
                            event.gpu_freq,
                            event.gpu_util,
                            toi.duration,
                            toi.cpu_cycles,
                            toi.energy[1],
                            toi.energy[0],
                            toi.dependency.type,
                            toi.dependency.prev_task.id
                            if toi.dependency.prev_task else "None",
                            self.pname,
                            self.tname,
                            toi.__class__.__name__,
                            toi.id,
                        ))

                    self.graph.add_node(
                        self.tasks[-1],
                        label=label,
                        fillcolor="darkolivegreen3",
                        style="filled,bold,rounded",
                        shape="box",
                    )

                    if subgraph:
                        self.graph.add_edge(
                            self.tasks[-1],
                            self.tasks[-1].events[0],
                            color="blue",
                            dir="forward",
                        )
                        self.graph.add_edge(
                            self.tasks[-1],
                            self.tasks[-1].events[-1],
                            color="red",
                            dir="back",
                        )

                    return

                else:
                    self.tasks[-1].add_event(event, subgraph=subgraph)

        elif event_type == JobType.SCHED_SWITCH_IN:

            if event.cpu != self.cpu:  # If the CPU has changed

                self._handle_cpu_num_change(event)

            if self.active is False:  # New task starting

                self.tasks.append(TaskNode(self.graph, self.pid, self.tname))
                self.tasks[-1].add_event(event, subgraph=subgraph)
                self.active = True

                if (len(self.tasks) >= 2
                    ):  # Connecting task in the same PID branch for visual aid
                    self.graph.add_edge(
                        self.tasks[-2],
                        self.tasks[-1],
                        color="lightseagreen",
                        style="dashed",
                    )
                    if self.tasks[-1].dependency.type != DependencyType.BINDER:
                        self.tasks[-1].dependency.type = DependencyType.TASK

                    # Create dependency from current task to calling task
                    if not self.tasks[
                            -1].dependency.prev_task:  # If not already set because of a Binder dependency
                        self.tasks[-1].dependency.prev_task = self.tasks[-2]

                    # Create dependency from calling task to current task
                    if not self.tasks[-2].dependency.next_task:
                        self.tasks[-2].dependency.next_task = self.tasks[-1]

                return

        elif event_type == JobType.BINDER_SEND:

            self.binder_tasks.append(
                BinderNode(self.graph, self.pid, self.tname))
            self.binder_tasks[-1].add_event(event, subgraph=subgraph)

            return

        elif event_type == JobType.BINDER_RECV:
            btoi = self.binder_tasks[-1]
            btoi.add_event(event, subgraph=subgraph)
            btoi.finish()
            label = "{}.{} ==> {}.{}\nPID: {} Dest PID: {}\nType: {}\nTrans: {}\nThread: '{}'\nNode Type: {} ID: #{}".format(
                str(btoi.events[0].time)[:-6],
                str(btoi.events[0].time)[-6:],
                str(btoi.events[-1].time)[:-6],
                str(btoi.events[-1].time)[-6:],
                str(event.pid),
                str(event.target_pid),
                str(btoi.events[0].trans_type),
                str(event.transaction),
                str(btoi.name),
                str(btoi.__class__.__name__),
                btoi.id,
            )
            self.graph.add_node(btoi,
                                label=label,
                                fillcolor="coral",
                                style="filled,bold",
                                shape="box")

            return

        # All other job types just need to get added to the task
        self.tasks[-1].add_event(event, subgraph=subgraph)
