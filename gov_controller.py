#Alex Hoffman 2019

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
        self.freq_table = self.GetCoreFreqs()
        print (self.freq_table)

    #TODO remove hardcoded stuff here
    def GetCoreFreqs(self):
        if self.core_type is 0:
            return GovStatus.adbIface.run_command(
                "cat /sys/devices/system/cpu/cpufreq/mp-cpufreq/cpu_freq_table").splitlines()[0].split()
        else:
            return GovStatus.adbIface.run_command(
                "cat /sys/devices/system/cpu/cpufreq/mp-cpufreq/kfc_freq_table").splitlines()[0].split()


class GovStatus:

    adbIface = adbInterface();

    def GetCores(self):
        cpus = GovStatus.adbIface.run_command(
                "ls /sys/devices/system/cpu | busybox grep -E 'cpu[0-9]+'")
        cpus = cpus.splitlines()
        self.core_count = len(cpus)
        for x in cpus:
            self.SetCoreOn(x)
            core_freq = int(GovStatus.adbIface.run_command(
                    "cat /sys/devices/system/cpu/" + x + "/cpufreq/cpuinfo_cur_freq"))
            core_type = int(GovStatus.adbIface.run_command(
                    "cat /sys/devices/system/cpu/" + x + "/topology/physical_package_id"))
            self.cores.append(Core(x, core_freq, 1, core_type))

    def SetCoreFreqs(self, freqs=[]):
        if not freqs:
            return
        #TODO check freq validity

        for x,f in enumerate(freqs):
            if f is 0:
                self.SetCoreOff(self.cores[x].name)
            else:
                self.SetCoreOn(self.cores[x].name)
                command = "echo " + str(f) + " > /sys/devices/system/cpu/" \
                    + self.cores[x].name + "/cpufreq/scaling_min_freq"
                GovStatus.adbIface.run_command(command)
                command = "echo " + str(f) + " > /sys/devices/system/cpu/" \
                    + self.cores[x].name + "/cpufreq/scaling_max_freq"
                GovStatus.adbIface.run_command(command)

    def SetCoreOn(self, core):
        GovStatus.adbIface.run_command(
                "echo 1 > /sys/devices/system/cpu/" + core + "/online")

    def SetCoreOff(self, core):
        GovStatus.adbIface.run_command(
                "echo 0 > /sys/devices/system/cpu/" + core + "/online")

    def __init__(self):
        GovStatus.adbIface.run_command(
                "echo interactive > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        GovStatus.adbIface.run_command(
                "echo interactive > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor")
        self.cores = []
        self.GetCores()
        for x,core in enumerate(self.cores):
            print (core.name)
            print (core.freq)
