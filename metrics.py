import csv
import sys
import time

from enum import Enum

from xu3_profile import XU3RegressionConstants


class TempLogEntry:

    def __init__(self, ts, big0, big1, big2, big3, little, gpu):
        self.time = ts
        self.big = [big0, big1, big2, big3]
        self.little = little
        self.gpu = gpu


class IdleState(Enum):
    is_idle = 0
    is_not_idle = 1


class UtilizationSlice:

    def __init__(self, start_time, util=0):
        self.start_time = start_time
        self.util = util


class CPUUtilizationSlice(UtilizationSlice):

    def __init__(self, start_time, finish_time, freq, state=0, util=0):
        UtilizationSlice.__init__(self, start_time, util)
        self.duration = (finish_time - 1) - start_time
        self.state = state
        self.freq = freq


class UtilizationTable:

    def __init__(self):
        self.initial_time = 0
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

    def get_util(self, time):

        event_time = time - self.initial_time - 1

        try:
            return self.utils[event_time]
        except IndexError:
            return 0.0

    def add_idle_event(self, event):
        # First event
        # TODO once the first event is found, account for the period before it (since beginnign)
        #  that was probably the inverse state to it's current state
        if self.initial_time is 0:
            self.initial_time = event.time
            if event.state == 4294967295:
                self.core_state = IdleState.is_not_idle
            else:
                self.core_state = not event.state
            return
        else:
            self.events.append(CPUUtilizationSlice(
                self.last_event_time, event.time - self.initial_time,
                SystemMetrics.current_metrics.core_freqs[event.cpu], state=self.core_state))

        self.last_event_time = event.time - self.initial_time
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

        self.initial_time = min(core.initial_time for core in cores)
        self.end_time = 0
        start_time = time.time()

        # get the starting and finishing time of the events on each core
        for core in cores:
            if len(core.events) != 0:
                if (self.initial_time + core.events[-1].start_time + core.events[-1].duration) > self.end_time:
                    self.end_time = self.initial_time + core.events[-1].start_time + core.events[-1].duration
        print ("Start and finish times took %s seconds" % (time.time() - start_time))

        start_time = time.time()

        # Compile util lookup tables for each core
        for core in cores:
            core.compile_lookup(self.initial_time, self.end_time)
        print ("Lookup tables took %s seconds" % (time.time() - start_time))

        return


class GPUUtilizationTable(UtilizationTable):

    def __init__(self):
        UtilizationTable.__init__(self)
        self.current_util = 0

    def init(self, time, util):
        self.initial_time = time
        self.current_util = util

    def add_mali_event(self, event):
        self.events.append(CPUUtilizationSlice(
            self.last_event_time, event.time - self.initial_time,
            freq=event.freq, util=self.current_util))

        self.current_util = event.util
        self.last_event_time = event.time - self.initial_time

    def get_GPU_cycle_energy(self, freq, util, temp):
        EP = SystemMetrics.current_metrics.energy_profile
        try:
            voltage = EP.GPU_voltages[freq]
        except Exception:
            print "Attempted to get GPU voltage with invalid freq"
            sys.exit(1)
        a1 = EP.GPU_reg_const["a1"]
        a2 = EP.GPU_reg_const["a2"]
        a3 = EP.GPU_reg_const["a3"]
        energy = voltage * (a1 * voltage * freq * util + a2 * temp + a3)
        return energy

    def calc_GPU_power(self, start_time, finish_time):

        energy = 0

        # if finish_time == 0:
        #     relative_finish_time = self.events[-1].time + self.events[-1].duration
        # else:
        #     relative_finish_time = finish_time - self.initial_time
        #
        # if start_time == 0:
        #     relative_start_time = 0
        # else:
        #     relative_start_time = start_time - self.initial_time

        # # iterate through power events
        # for x, event in enumerate(self.events):
        #     # find start event
        #     if (relative_start_time >= event.start_time) and (relative_start_time < (event.start_time + event.duration)):
        #         temp = SystemMetrics.current_metrics.get_temp(event.start_time, -1)  # -1 for GPU
        #         cycle_energy = self.get_GPU_cycle_energy(event.freq, event.util, temp)
        #         cycles = (event.duration - relative_start_time - event.start_time) * 0.000000001 * event.frequency
        #     # end case
        #     elif (relative_finish_time >= event.start_time) and (relative_finish_time < (event.start_time + event.duration)):
        #         temp = SystemMetrics.current_metrics.get_temp(event.start_time, -1)
        #         cycle_energy = self.get_GPU_cycle_energy(event.freq, event.util, temp)
        #         cycles = (event.duration - relative_finish_time - event.start_time) * 0.000000001 * event.frequency
        #     # middle cases
        #     elif (relative_start_time < event.start_time) and (relative_finish_time > (event.start_time + event.duration)):
        #         temp = SystemMetrics.current_metrics.get_temp(event.start_time, -1)
        #         cycle_energy = self.get_GPU_cycle_energy(event.freq, event.util, temp)
        #         cycles = event.duration * 0.000000001 * event.frequency
        #
        #     energy += cycle_energy * cycles

        for x, event in enumerate(self.events):
            temp = SystemMetrics.current_metrics.get_temp(event.start_time, -1)
            cycle_energy = self.get_GPU_cycle_energy(event.freq, event.util, temp) / event.freq
            cycles = event.duration * 0.000000001 * event.freq
            energy += cycle_energy * cycles

        return energy


class SystemUtilization:

    def __init__(self, core_count):
        self.core_utils = []
        self.cluster_utils = []
        self.init_tables(core_count)
        self.gpu_utils = GPUUtilizationTable()

    def init_tables(self, core_count):
        for x in range(core_count):
            self.core_utils.append(CPUUtilizationTable(x))
        # TODO remove magic number
        for x in range(2):
            self.cluster_utils.append(TotalUtilizationTable())


class SystemTemps:

    def __init__(self, cluster_count, cluster_cores):
        self.temps = []
        self.initial_time = 0
        self.end_time = 0


class SystemMetrics:
    current_metrics = None

    def __init__(self, adb, filename):
        self.adb = adb
        self.energy_profile = XU3RegressionConstants()
        self.core_count = self.get_core_count()
        self.core_freqs = self.get_core_freqs()
        self.core_utils = self.get_core_utils()
        self.gpu_freq = self.get_GPU_freq()
        self.gpu_util = self.get_GPU_util()
        self.sys_util = SystemUtilization(self.core_count)
        self.sys_temps = SystemTemps(2, 4)  # TODO remove magic numbers
        self.unprocessed_temps = []
        self.save_to_file(filename)

        SystemMetrics.current_metrics = self

    def save_to_file(self, filename):
        with open("/tmp/" + filename + "_metrics.csv", "w+") as f:
            writer = csv.writer(f, delimiter=',')
            writer.writerow([self.core_count])
            core_freqs = []
            core_utils = []
            for i in range(self.core_count):
                core_freqs.append(str(self.core_freqs[i]))
                core_utils.append(str(self.core_utils[i]))
            writer.writerow(core_freqs)
            writer.writerow(core_utils)
            writer.writerow([self.gpu_freq])
            writer.writerow([self.gpu_util])

    def load_from_file(self, filename):
        with open("/tmp/" + filename + "_metrics.csv", "r") as f:
            data = csv.reader(f)
            self.core_freqs = []
            self.core_utils = []
            for x, row in enumerate(data):
                if x == 0:
                    self.core_count = int(row[0])
                elif x == 1:
                    for i in range(self.core_count):
                        self.core_freqs.append(int(row[i]))
                elif x == 2:
                    for i in range(self.core_count):
                        self.core_utils.append(int(row[i]))
                elif x == 3:
                    self.gpu_freq = int(row[0])
                elif x == 4:
                    self.gpu_util = int(row[0])

    def get_core_count(self):
        return int(self.adb.run_command("nproc"))

    def get_core_freqs(self):
        frequencies = []
        for core in range(self.core_count):
            frequencies.append(
                int(self.adb.run_command("cat /sys/devices/system/cpu/cpu"
                                         + str(core) + "/cpufreq/scaling_cur_freq")) * 1000)
        return frequencies

    def get_core_utils(self):
        # TODO
        loads = [0] * self.core_count
        return loads

    def get_GPU_freq(self):
        return int(self.adb.run_command("cat /sys/class/misc/mali0/device/clock"))

    def get_GPU_util(self):
        return int(self.adb.run_command("cat /sys/class/misc/mali0/device/utilization"))

    def get_CPU_core_freq(self, core):
        return self.core_freqs[core]

    def get_GPU_core_freq(self):
        return self.gpu_freq

    def write_core_freqs_to_file(self, filename):
        with open(filename, "w+") as f:
            data = f.read()
            for x in range(self.core_count):
                f.write(str(x) + " " + str(self.core_freqs[x]) + "\n" + data)
            f.close()

    def get_average_cpu_temp(self, entry):
        temp = 0
        for i in range(4):
            temp += entry.cpus[i]
        temp /= 4.0

        return temp

    # Core of -1 is GPU
    def get_temp(self, ts, core):
        # If time is before first temp recording then default to fire temp recording
        try:
            if ts <= self.sys_temps.temps[0].time:
                if core == -1:
                    return self.sys_temps.temps[0].gpu
                elif core <= 3:
                    return self.sys_temps.temps[0].little
                else:
                    return self.sys_temps.temps[0].big[core % 4]
            elif ts >= self.sys_temps.temps[-1].time:
                if core == -1:
                    return self.sys_temps.temps[-1].gpu
                elif core <= 3:
                    return self.sys_temps.temps[-1].little
                else:
                    return self.sys_temps.temps[-1].big[core % 4]
            else:
                if core == -1:
                    return self.sys_temps.temps[ts - self.sys_temps.initial_time].gpu
                elif core <= 3:
                    return self.sys_temps.temps[ts - self.sys_temps.initial_time].little
                else:
                    return self.sys_temps.temps[ts - self.sys_temps.initial_time].big[core % 4]
        except Exception:
            print "Temperature cound not be retrieved for time %d" % ts
            sys.exit(1)

    def compile_temps_table(self):
        self.sys_temps.initial_time = self.unprocessed_temps[0].time
        self.sys_temps.end_time = self.unprocessed_temps[-1].time

        for i, event in enumerate(self.unprocessed_temps[:-1]):
            for t in range(self.unprocessed_temps[i].time - self.sys_temps.initial_time,
                           self.unprocessed_temps[i + 1].time - self.sys_temps.initial_time):
                self.sys_temps.temps.append(event)

        # append final temp event as this will be for all times > than last event
        self.sys_temps.temps.append(self.unprocessed_temps[-1])
