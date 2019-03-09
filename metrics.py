from enum import Enum

class IdleState(Enum):
    is_idle = 0
    is_not_idle = 1


class UtilizationSlice:

    def __init__(self, start_time, finish_time, state):
        self.start_time = start_time
        self.duration = (finish_time - 1) - start_time
        self.state = state
        self.utilization = 0


class UtilizationTable:

    def __init__(self):
        self.initial_time = 0
        self.last_event_time = 0
        self.core_state = 0
        self.events = []

    def add_event(self, event):
        # First event
        if self.initial_time is 0:
            self.initial_time = event.time
            self.last_event_time = 0
            if event.state == 4294967295:
                self.core_state = IdleState.is_not_idle
            else:
                self.core_state = not event.state
            return
        else:
            self.events.append(UtilizationSlice(
                self.last_event_time, event.time - self.initial_time, self.core_state))

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

            if calc_duration >= 250000:
                break

        self.events[-1].utilization = float(active_duration)/float(calc_duration) * 100.00


class SystemUtilization:

    def __init__(self, core_count):
        self.core_utils = []
        self.init_tables(core_count)

    def init_tables(self, core_count):
        for x in range(core_count):
            self.core_utils.append(UtilizationTable())

class SystemMetrics:

    current_metrics = None

    def __init__(self, adb, energy_profile):
        self.adb = adb
        self.energy_profile = energy_profile
        self.core_count = self.get_core_count()
        self.core_freqs = self.get_core_freqs()
        self.core_utils = self.get_core_utils()
        self.gpu_freq = self.get_GPU_freq()
        self.gpu_util = self.get_GPU_util()
        self.sys_util = SystemUtilization(self.core_count)

        SystemMetrics.current_metrics = self

    def get_core_count(self):
        return int(self.adb.run_command("nproc"))

    def get_core_freqs(self):
        frequencies = []
        for core in range(self.core_count):
            frequencies.append(
                int(self.adb.run_command("cat /sys/devices/system/cpu/cpu"
                                         + str(core) + "/cpufreq/scaling_cur_freq")))
        return frequencies

    def get_core_utils(self):
        #TODO
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
