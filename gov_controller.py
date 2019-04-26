#Alex Hoffman 2019
from adbinterface import adbInterface
from enum import Enum

class core_type(Enum):
    big = 0
    little = 1

class Core:

    def __init__(self, name, freq, freq_table, online=1, bigLITTLE=core_type.little.value):
        self.name = name
        self.core_type = bigLITTLE
        if bigLITTLE is 0:
            self.online = online
        else:
            self.online = 1
        self.freq = freq
        self.freq_table = freq_table

class GovStatus:

    def GetCores(self):
        cpus = self.adbIface.command(
                "ls /sys/devices/system/cpu | busybox grep -E 'cpu[0-9]+'")
        cpus = cpus.splitlines()
        self.core_count = len(cpus)
        for x in cpus:
            self.SetCoreOn(x)
            core_freq = int(self.adbIface.command(
                    "cat /sys/devices/system/cpu/" + x + "/cpufreq/cpuinfo_cur_freq"))
            core_type = int(self.adbIface.command(
                    "cat /sys/devices/system/cpu/" + x + "/topology/physical_package_id"))
            if core_type is 0:
                freqs = self.adbIface.command(
                    "cat /sys/devices/system/cpu/cpufreq/mp-cpufreq/cpu_freq_table").splitlines()[0].split()
            else:
                freqs = self.adbIface.command(
                    "cat /sys/devices/system/cpu/cpufreq/mp-cpufreq/kfc_freq_table").splitlines()[0].split()
            self.cores.append(Core(x, core_freq, freqs, 1, core_type))

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
                self.adbIface.command(command)
                command = "echo " + str(f) + " > /sys/devices/system/cpu/" \
                    + self.cores[x].name + "/cpufreq/scaling_max_freq"
                self.adbIface.command(command)

    def SetCoreOn(self, core):
        self.adbIface.command(
                "echo 1 > /sys/devices/system/cpu/" + core + "/online")

    def SetCoreOff(self, core):
        self.adbIface.command(
                "echo 0 > /sys/devices/system/cpu/" + core + "/online")

    def DisconnectADB(self):
        del self.adbIface

    def ConnectADB(self):
        try:
            self.adbIface
        except AttributeError:
            self.adbIface = adbInterface()

    def __init__(self):
        self.adbIface = adbInterface();
        self.adbIface.command(
                "echo interactive > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        self.adbIface.command(
                "echo interactive > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor")
        self.cores = []
        self.GetCores()


