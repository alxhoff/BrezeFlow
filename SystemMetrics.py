#!/usr/bin/env python

import sys

import numpy as np

from XU3EnergyProfile import XU3RegressionModel

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class TempLogEntry:
    """ Stores a snapshot of the system's temperatures at a given timestamp.
    """

    def __init__(self, ts, big0, big1, big2, big3, little, gpu):
        self.time = ts
        self.big = [big0, big1, big2, big3]
        self.little = little
        self.gpu = gpu


class SystemTemps:
    """ A timeline of system temperature snapshots.
    """

    def __init__(self):
        self.temps = []
        self.initial_time = 0
        self.end_time = 0


class UtilizationSlice:
    """ Records a slice of a utilization timeline.
        """

    def __init__(self, start_time, finish_time, freq=0, state=0, util=0):
        self.start_time = start_time
        self.util = util
        self.duration = (finish_time - 1) - start_time
        self.state = state
        self.freq = freq


class UtilizationTable:

    def __init__(self):
        self.start_time = 0
        self.last_event_time = 0
        self.core_state = 0
        self.events = []


class UtilizationWindow:

    def __init__(self, window_duration):

        self.window_duration = window_duration
        self.buffer_duration = 0
        self.on_time = 0
        self.entries = []

    def add_state(self, state, duration):

        if self.buffer_duration + duration > self.window_duration:
            self.remove_duration_front(self.buffer_duration + duration - self.window_duration)

        self.add_state_entry(state, duration)

    def add_state_entry(self, state, duration):
        self.entries.append([state, duration])
        self.buffer_duration += duration
        if state:
            self.on_time += duration

    def remove_states(self, indicies):
        for index in reversed(indicies):
            if self.entries[index][0]:
                self.on_time -= self.entries[index][1]
            self.buffer_duration -= self.entries[index][1]

            del self.entries[index]

    def remove_duration_front(self, duration):
        entries_to_delete = []

        while duration:
            for x, entry in enumerate(self.entries):
                if entry[1] <= duration:
                    entries_to_delete.append(x)
                    duration -= entry[1]
                else:
                    entry[1] = entry[1] - duration
                    self.buffer_duration -= duration
                    if entry[0]:
                        self.on_time -= duration
                    duration = 0
                    break

        self.remove_states(entries_to_delete)

    def calculate_util(self):

        return float(self.on_time) / self.buffer_duration * 100.0


class CPUUtilizationTable(UtilizationTable):

    def __init__(self, core_num):
        UtilizationTable.__init__(self)

        self.uw = UtilizationWindow(250000)
        self.core = core_num
        self.utils = []

    def get_util(self, ts):

        try:
            return self.utils[ts - self.start_time - 1]
        except IndexError:
            return 0.0

    def add_idle_event(self, event):

        if self.start_time is 0:  # First event
            self.start_time = event.time
            self.last_event_time = 0
            self.core_state = event.state
            return

        duration = event.time - self.start_time - self.last_event_time
        self.uw.add_state(self.core_state, duration)
        util = self.uw.calculate_util()
        util_array = np.full(duration, [util])
        np.concatenate((self.utils, util_array))

        self.last_event_time = event.time - self.start_time
        self.core_state = event.state


class GPUUtilizationTable(UtilizationTable):

    def __init__(self):
        UtilizationTable.__init__(self)
        self.current_util = 0
        self.finish_time = 0

    def init(self, start_time, finish_time, util):
        """ Sets the initial values for the GPU.

        :param start_time:
        :param finish_time:
        :param util:
        :return:
        """
        self.start_time = start_time
        self.finish_time = finish_time
        self.current_util = util

    def add_event(self, event):
        self.events.append(UtilizationSlice(
                self.last_event_time, event.time - self.start_time,
                freq=event.freq, util=self.current_util))

        self.current_util = event.util
        self.last_event_time = event.time - self.start_time

    def get_util(self, ts):

        for x, event in enumerate(self.events):
            if event.start_time <= ts < (event.start_time + event.duration):
                return event.util

        return 0

    def get_freq(self, ts):

        for x, event in enumerate(self.events):
            if event.start_time <= ts < (event.start_time + event.duration):
                return event.freq

        return 0

    def get_energy(self, start_time, finish_time):
        """ Sums the energy consumption of the GPU between the specified times.

        :param start_time: Time at which the summing of the GPU's energy consumption should start
        :param finish_time: Time at which the summing of the GPU's energy consumption should stop
        :return: The summed energy (in joules) between the specified timestamps
        """

        energy = 0

        if finish_time == 0:
            relative_finish_time = self.events[-1].time + self.events[-1].duration
        else:
            relative_finish_time = finish_time - self.start_time

        if start_time == 0:
            relative_start_time = 0
        else:
            relative_start_time = start_time - self.start_time
            if relative_start_time < 0:
                relative_start_time = 0

        for x, event in enumerate(self.events):
            cycles = 0

            temp = SystemMetrics.current_metrics.get_temp(event.start_time + self.start_time, -1)

            assert (temp != 0), "GPU temp found to be zero at time %d" % (event.start_time + self.start_time)

            cycle_energy = XU3RegressionModel.get_gpu_cycle_energy(event.freq, event.util, temp) / event.freq

            assert (cycle_energy != 0), "freq: %d, util: %d, temp: %d" % (event.freq, event.util, temp)

            #  Start event
            if (relative_start_time >= event.start_time) and \
                    (relative_start_time < (event.start_time + event.duration)):

                duration = (event.duration - (relative_start_time - event.start_time)) * 0.000001
                cycles = duration * event.freq

                assert (cycles != 0), "duration: %d, relative start: %d, start time: %d, freq: %d, cycles: %d" \
                                      % (event.duration, relative_start_time, event.start_time, event.freq, cycles)
            #  End event
            elif (relative_finish_time >= event.start_time) and (
                    relative_finish_time < (event.start_time + event.duration)):

                duration = (event.duration - (relative_finish_time - event.start_time)) * 0.000001
                cycles = duration * event.freq

                assert (cycles != 0), "duration: %d, relative finish: %d, start time: %d, freq: %d, cycles: %d" \
                                      % (event.duration, relative_finish_time, event.start_time, event.freq, cycles)
            # Middle event
            elif (relative_start_time < event.start_time) and \
                    (relative_finish_time > (event.start_time + event.duration)):

                duration = event.duration * 0.000001
                cycles = duration * event.freq

                assert (cycles != 0), "Cycles could not be found for GPU"

            elif event.start_time >= relative_finish_time:
                return energy

            energy += cycle_energy * cycles

        return energy

    def get_interval_energy(self, second, interval, start_time, finish_time):
        """ Returns the energy consumption (in joules) between the two timestamps, offset by a number of seconds.

        :param second: Number of seconds that the summed second should be offset from the start timestamp
        :param interval: The size of the measurement interval as a fraction of a second, ie. 200ms = 0.2
        :param start_time: Start time from which the second sums should be referenced in time
        :param finish_time: Timestamp which no sum should go over
        :return: The energy (in joules) of the second
        """
        microsecond_start = start_time + (second * interval * 1000000)
        microsecond_finish = microsecond_start + interval * 1000000
        if finish_time < microsecond_finish:
            microsecond_finish = finish_time

        return self.get_energy(microsecond_start, microsecond_finish)


class SystemUtilization:

    def __init__(self, core_count):
        self.cpu = []
        # self.clusters = []
        self.gpu = GPUUtilizationTable()
        self._init_tables(core_count)

    def _init_tables(self, core_count):
        for x in range(core_count):
            self.cpu.append(CPUUtilizationTable(x))
        # TODO remove magic number
        # for x in range(2):
        #     self.clusters.append(TotalUtilizationTable())


class SystemMetrics:
    """ Stores all current and previous system metrics for all relevant hardware from the target system.

    Attributes:
        adb                 The ADB connection used to interface with the target Android device.
        energy_profile      Regression constants used to calculate per-core energy consumption for target device.
        core_count          Number of cores on the target Android device.

        current_core_freqs  As the event timeline is processed the "current" core frequencies, utilizations are stored
        current_core_utils  for the CPUs and GPU, used for energy calculations
        current_gpu_freq
        current_gpu_util

        sys_util_history    A history of all utilizations for both the CPU and GPU
        sys_temp_history    A history of all temperature measurements for both the CPU and GPU
    """
    current_metrics = None

    def __init__(self, adb):
        self.adb = adb
        self.energy_profile = XU3RegressionModel()
        self.core_count = self._get_core_count()

        self.current_core_freqs = self._get_core_freqs()
        self.current_core_utils = self._get_core_utils()
        self.current_gpu_freq = self._get_gpu_freq()
        self.current_gpu_util = self._get_gpu_util()

        self.sys_util_history = SystemUtilization(self.core_count)
        self.sys_temp_history = SystemTemps()

        SystemMetrics.current_metrics = self

    def get_temp(self, ts, core):
        """ Returns the temperature for a particular core (GPU represented by core -1) at a particular point in time.
        If the time falls before or after the recorded temperature measurements then the first or last temperature will
        be returned respectively.

        :param ts: The time at which the temperature should be returned
        :param core: The core for which the temperature should be returned
        :return: The temperature of the specified core at the specified time
        """
        try:
            if ts <= self.sys_temp_history.temps[0].time:
                if core == -1:
                    return self.sys_temp_history.temps[0].gpu
                elif core <= 3:
                    return self.sys_temp_history.temps[0].little
                else:
                    return self.sys_temp_history.temps[0].big[core % 4]
            elif ts >= self.sys_temp_history.temps[-1].time:
                if core == -1:
                    return self.sys_temp_history.temps[-1].gpu
                elif core <= 3:
                    return self.sys_temp_history.temps[-1].little
                else:
                    return self.sys_temp_history.temps[-1].big[core % 4]
            else:
                if core == -1:
                    return self.sys_temp_history.temps[ts - self.sys_temp_history.initial_time].gpu
                elif core <= 3:
                    return self.sys_temp_history.temps[ts - self.sys_temp_history.initial_time].little
                else:
                    return self.sys_temp_history.temps[ts - self.sys_temp_history.initial_time].big[core % 4]
        except IndexError:
            print "Temperature could not be retrieved for time %d" % ts
            sys.exit(1)

    def _get_core_count(self):
        return int(self.adb.command("nproc"))

    def _get_core_freqs(self):
        frequencies = []
        for core in range(self.core_count):
            try:
                frequencies.append(
                        int(self.adb.command("cat /sys/devices/system/cpu/cpu"
                                             + str(core) + "/cpufreq/scaling_cur_freq")) * 1000)
            except ValueError:  # Big is off
                frequencies.append(0)

        return frequencies

    def _get_core_utils(self):
        loads = [0] * self.core_count
        return loads

    def _get_gpu_freq(self):
        return int(self.adb.command("cat /sys/class/misc/mali0/device/clock"))

    def _get_gpu_util(self):
        return int(self.adb.command("cat /sys/class/misc/mali0/device/utilization"))

    def get_cpu_core_freq(self, core):
        return self.current_core_freqs[core]


    def get_gpu_core_freq(self):
        return self.current_gpu_freq
