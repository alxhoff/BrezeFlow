#!/usr/bin/env python

import sys
import time

from enum import Enum

from XU3EnergyProfile import XU3RegressionConstants

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class IdleState(Enum):
    """ Used by idle trace events to track if a CPU is idle or not.
    """
    is_idle = 0
    is_not_idle = 1


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


class CPUUtilizationTable(UtilizationTable):

    def __init__(self, core_num):
        UtilizationTable.__init__(self)
        self.core = core_num
        self.utils = []

    def compile_lookup(self, start_time, end_time):
        lookup_length = end_time - start_time + 1
        self.utils = [0.0] * lookup_length
        if len(self.events) != 0:
            for event in self.events:
                util = round(event.util, 2)
                for x in range(event.duration + 1):
                    self.utils[x + event.start_time] = util
        return

    def get_util(self, ts):

        event_time = ts - self.start_time - 1

        try:
            return self.utils[event_time]
        except IndexError:
            return 0.0

    def add_idle_event(self, event):
        if self.start_time is 0:  # First event
            self.start_time = event.time
            if event.state == 4294967295:
                self.core_state = IdleState.is_not_idle
            else:
                self.core_state = not event.state
        else:
            self.events.append(UtilizationSlice(
                    self.last_event_time, event.time - self.start_time,
                    SystemMetrics.current_metrics.current_core_freqs[event.cpu], state=self.core_state))

            self.last_event_time = event.time - self.start_time
            self.calc_util_last_event()

            if event.state == 4294967295:
                self.core_state = not self.core_state
            else:
                self.core_state = event.state

    def calc_util_last_event(self):
        # Iterate backwards until 250ms has been traversed or until first event hit
        calc_duration = 0
        active_duration = 0
        for event in reversed(self.events):
            calc_duration += event.duration
            if event.state:
                active_duration += event.duration

            if calc_duration >= 25000:
                break

        self.events[-1].util = float(active_duration) / float(calc_duration) * 100.00


class TotalUtilizationTable(UtilizationTable):

    def __init__(self):
        UtilizationTable.__init__(self)
        self.end_time = 0
        self.slices = []

    def compile_table(self, cores):

        self.start_time = min(core.start_time for core in cores)
        self.end_time = 0
        start_time = time.time()

        # get the starting and finishing time of the events on each core
        for core in cores:
            if len(core.events) != 0:
                if (self.start_time + core.events[-1].start_time + core.events[-1].duration) > self.end_time:
                    self.end_time = self.start_time + core.events[-1].start_time + core.events[-1].duration
        print ("Start and finish times took %s seconds" % (time.time() - start_time))

        start_time = time.time()

        # Compile util lookup tables for each core
        for core in cores:
            core.compile_lookup(self.start_time, self.end_time)
        print ("Lookup tables took %s seconds" % (time.time() - start_time))

        return


def get_gpu_cycle_energy(freq, util, temp):
    energy_profile = SystemMetrics.current_metrics.energy_profile
    try:
        voltage = energy_profile.GPU_voltages[freq]
    except IndexError:
        print "Attempted to get GPU voltage with invalid freq"
        sys.exit(1)
    a1 = energy_profile.GPU_reg_const["a1"]
    a2 = energy_profile.GPU_reg_const["a2"]
    a3 = energy_profile.GPU_reg_const["a3"]
    energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
    return energy


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

            cycle_energy = get_gpu_cycle_energy(event.freq, event.util, temp) / event.freq
            assert (cycle_energy != 0), "freq: %d, util: %d, temp: %d" % (event.freq, event.util, temp)

            if (relative_start_time >= event.start_time) and \
                    (relative_start_time < (event.start_time + event.duration)):
                cycles = (event.duration - (relative_start_time - event.start_time)) * 0.000000001 * event.freq
                assert (cycles != 0), "duration: %d, relative start: %d, start time: %d, freq: %d, cycles: %d" \
                                      % (event.duration, relative_start_time, event.start_time, event.freq, cycles)
            elif (relative_finish_time >= event.start_time) and (
                    relative_finish_time < (event.start_time + event.duration)):
                cycles = (event.duration - (relative_finish_time - event.start_time)) * 0.000000001 * event.freq
                assert (cycles != 0), "duration: %d, relative finish: %d, start time: %d, freq: %d, cycles: %d" \
                                      % (event.duration, relative_finish_time, event.start_time, event.freq, cycles)
            elif (relative_start_time < event.start_time) and \
                    (relative_finish_time > (event.start_time + event.duration)):
                cycles = event.duration * 0.000000001 * event.freq
                assert (cycles != 0), "Cycles could not be found for GPU"

            elif event.start_time >= relative_finish_time:
                return energy

            energy += cycle_energy * cycles

        return energy

    def get_second_energy(self, second, start_time, finish_time):
        """ Returns the energy consumption (in joules) between the two timestamps, offset by a number of seconds.

        :param second: Number of seconds that the summed second should be offset from the start timestamp
        :param start_time: Start time from which the second summs should be referenced in time
        :param finish_time: Timestamp which no sum should go over
        :return: The energy (in joules) of the second
        """
        nanosecond_start = start_time + (second * 1000000)
        nanosecond_finish = nanosecond_start + 1000000
        if finish_time < nanosecond_finish:
            nanosecond_finish = finish_time

        return self.get_energy(nanosecond_start, nanosecond_finish)


class SystemUtilization:

    def __init__(self, core_count):
        self.cpu = []
        self.clusters = []
        self.gpu = GPUUtilizationTable()
        self._init_tables(core_count)

    def _init_tables(self, core_count):
        for x in range(core_count):
            self.cpu.append(CPUUtilizationTable(x))
        # TODO remove magic number
        for x in range(2):
            self.clusters.append(TotalUtilizationTable())


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
        self.energy_profile = XU3RegressionConstants()
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
            frequencies.append(
                    int(self.adb.command("cat /sys/devices/system/cpu/cpu"
                                         + str(core) + "/cpufreq/scaling_cur_freq")) * 1000)
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

    def _get_gpu_core_freq(self):
        return self.current_gpu_freq
