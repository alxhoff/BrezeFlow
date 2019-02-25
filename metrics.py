class SystemMetrics:

    def __init__(self, adb):
        self.adb = adb
        self.core_count = self.getCoreCount()
        self.core_freqs = self.getCoreFrequencies()
        self.gpu_freq = self.getGPUFreq()
        self.gpu_util = self.getGPUUtil()

    def getCoreCount(self):
        return int(self.adb.runCommand("nproc"))

    def getCoreFrequencies(self):
        frequencies = []
        for core in range(self.core_count):
            frequencies.append(
                int(self.adb.runCommand("cat /sys/devices/system/cpu/cpu"
                                        + str(core) + "/cpufreq/scaling_cur_freq")))
        return frequencies

    def getGPUFreq(self):
        return int(self.adb.runCommand("cat /sys/class/misc/mali0/device/clock"))

    def getGPUUtil(self):
        return int(self.adb.runCommand("cat /sys/class/misc/mali0/device/utilization"))

    def writeCoreFreqsToFile(self, filename):
        with open(filename, "w+") as f:
            data = f.read()
            for x in range(self.core_count):
                f.write(str(x) + " " + str(self.core_freqs[x]) + "\n" + data)
            f.close()
