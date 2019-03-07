class SystemMetrics:

    current_metrics = None

    def __init__(self, adb, little_freqs, little_energy, big_freqs, big_energy, gpu_freqs, gpu_energy):
        self.adb = adb
        self.little_freqs = little_freqs
        self.little_energy = little_energy
        self.big_freqs = big_freqs
        self.big_energy = big_energy
        self.gpu_freqs = gpu_freqs
        self.gpu_energy = gpu_energy
        self.core_count = self.get_core_count()
        self.core_freqs = self.get_core_freqs()
        self.core_utils = self.get_core_utils()
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
