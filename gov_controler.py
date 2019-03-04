from adbinterface import adbInterface
from enum import Enum

class core_type(Enum):
    big = 0
    little = 1

class Core:

    def __init__(self, name, freq, online=1, bigLITTLE=core_type.little.value):
        self.name = name
        self.core_type = bigLITTLE
        if bigLITTLE is 0:
            self.online = online
        else:
            self.online = 1
        self.freq = freq

class GovStatus:

    adbIface = adbInterface();

    def GetCores(self):
        cpus = GovStatus.adbIface.run_command(
                "ls /sys/devices/system/cpu | busybox grep -E 'cpu[0-9]+'")
        cpus = cpus.splitlines()
        self.core_count = len(cpus)
        for x in cpus:
            core_freq = int(GovStatus.adbIface.run_command(
                    "cat /sys/devices/system/cpu/" + x + "/cpufreq/cpuinfo_cur_freq"))
            core_type = GovStatus.adbIface.run_command(
                    "cat /sys/devices/system/cpu/" + x + "/topology/physical_package_id")
            if core_type:
                self.cores.append(Core(x, core_freq, core_type))

    def SetCoreFreqs(self, freqs=[]):
        if not freqs:
            return
        #TODO check freq validity

        for x,f in enumerate(freqs):
            command = "echo " + str(f) + " > /sys/devices/system/cpu/" \
                + self.cores[x].name + "/cpufreq/scaling_min_freq"
            GovStatus.adbIface.run_command(command)
            command = "echo " + str(f) + " > /sys/devices/system/cpu/" \
                + self.cores[x].name + "/cpufreq/scaling_max_freq"
            GovStatus.adbIface.run_command(command)

    def SetBigOn(self):
        GovStatus.adbIface.run_command(
                "echo 1 > /sys/devices/system/cpu/cpu5/online")

    def SetBigOff(self):
        GovStatus.adbIface.run_command(
                "echo 0 > /sys/devices/system/cpu/cpu5/online")

    def __init__(self):
        self.SetBigOn()
        GovStatus.adbIface.run_command(
                "echo interactive > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        GovStatus.adbIface.run_command(
                "echo interactive > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor")
        self.cores = []
        self.GetCores()
        for x,core in enumerate(self.cores):
            print core.name
            print core.freq

g_stats = GovStatus()
g_stats.SetCoreFreqs([1100000,1100000,1100000])

