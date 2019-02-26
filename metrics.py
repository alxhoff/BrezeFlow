class SystemMetrics:

    current_metrics = None

    def __init__(self, adb):
        self.adb = adb
        self.core_count = self.get_core_count()
        self.core_freqs = self.get_core_freqs()
        self.core_loads = self.get_core_loads()
        self.gpu_freq = self.get_GPU_freq()
        self.gpu_util = self.get_GPU_util()

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

    def get_core_loads(self):
        #TODO
        loads = [0] * self.core_count
        return loads

    def get_GPU_freq(self):
        return int(self.adb.run_command("cat /sys/class/misc/mali0/device/clock"))

    def get_GPU_util(self):
        return int(self.adb.run_command("cat /sys/class/misc/mali0/device/utilization"))

    def get_CPU_core_freq(self, core):
        return self.core_freqs[core]

    def write_core_freqs_to_file(self, filename):
        with open(filename, "w+") as f:
            data = f.read()
            for x in range(self.core_count):
                f.write(str(x) + " " + str(self.core_freqs[x]) + "\n" + data)
            f.close()
