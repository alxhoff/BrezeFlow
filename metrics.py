from enum import Enum

class IdleState(Enum):
    is_idle = 0
    is_not_idle = 1

class UtilizationSlice:

    def __init__(self, start_time, util=0):
        self.start_time = start_time
        self.utilization = util


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

            if calc_duration >= 250000:
                break

        self.events[-1].utilization = float(active_duration) / float(calc_duration) * 100.00

class TotalUtilizationTable(UtilizationTable):

    def __init__(self):
        UtilizationTable.__init__(self)
        self.end_time = 0
        self.slices = []

    def compile_table(self, cores):
        core_count = len(cores)
        self.initial_time = min(core.initial_time for core in cores)
        self.end_time = max((event.events[-1].start_time + event.events[-1].duration) for event in cores)

        for x in range(self.end_time):
            util = 0.0

            for core in range(core_count):
                util += SystemMetrics.current_metrics.sys_util.get_util_from_idle_events(core, x + self.initial_time)

            util /= core_count

            self.slices.append(UtilizationSlice(x, util))

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

    @staticmethod
    def get_cycle_energy(self, freq, util):
        for entry in SystemMetrics.current_metrics.energy_profile.gpu_values:
            if entry.frequency == freq:
                return entry.alpha * util + entry.beta
        return 0

    def calc_GPU_power(self, start_time, finish_time):
        relative_start_time = start_time - self.initial_time
        relative_finish_time = finish_time - self.initial_time
        energy = 0
        cycle_energy = 0
        cycles = 0
        # iterate through power events
        for x, event in enumerate(self.events):
            # find start event
            if (relative_start_time >= event.time) and (relative_start_time < (event.time + event.duration)):
                cycle_energy = self.get_cycle_energy(event.freq, event.util)
                cycles = (event.duration - relative_start_time - event.start_time) * 0.000001 * event.frequency
            # end case
            elif (relative_finish_time >= event.time) and (relative_finish_time < (event.time + event.duration)):
                cycle_energy = self.get_cycle_energy(event.freq, event.util)
                cycles = (event.duration - relative_finish_time - event.start_time) * 0.000001 * event.frequency
            # middle cases
            elif (relative_start_time < event.time) and (relative_finish_time > (event.time + event.duration)):
                cycle_energy = self.get_cycle_energy(event.freq, event.util)
                cycles = event.duration * 0.000001 * event.frequency

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

    def get_util_from_idle_events(self, core, time):
        if core == -1:
            core_util = self.gpu_utils
        else:
            core_util = self.core_utils[core]

        event_time = time - core_util.initial_time

        # before first util calc
        if event_time < 0:
            return 0.0

        # start walking events to find util
        for slice in core_util.events:
            if (event_time >= slice.start_time) \
                    and (event_time < (slice.start_time + slice.duration)):
                return slice.utilization
        return 0.0


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
                                         + str(core) + "/cpufreq/scaling_cur_freq")) * 1000)
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
