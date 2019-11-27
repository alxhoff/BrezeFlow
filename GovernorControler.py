#!/usr/bin/env python
"""
The Governor Controller provides an easy to use interface to control the CPUFreq governor on Android devices.
"""

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

from ADBInterface import ADBInterface


class GovernorController:
    available_governors = []
    little_name = "kfc"
    big_name = "cpu"

    def get_governors(self):
        adb = ADBInterface()
        return adb.command(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"
        ).split()

    def get_current_governor(self):
        governors = ["",""]
        adb = ADBInterface()

        governors[0] = adb.command(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").split(
            )[0]
        governors[1] = adb.command(
                "cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor").split(
                )[0]
        return governors

    def set_big_online(self, state):
        adb = ADBInterface()

        if state:
            for i in range(4):
                adb.command("echo 1 > /sys/devices/system/cpu/cpu{}/online 2> /dev/null".format(i))
        else:
            for i in range(4):
                adb.command("echo 0 > /sys/devices/system/cpu/cpu{}/online 2> /dev/null".format(i))

    def set_hotplug_online(self, state):

        adb = ADBInterface()

        if state:
            adb.command("echo 1 > /sys/power/enable_dm_hotplug")
        else:
            adb.command("echo 0 > /sys/power/enable_dm_hotplug")

    def set_governor(self, governor):
        self.set_big_online(True)
        self.set_hotplug_online(False)

        adb = ADBInterface()

        adb.command(
            "echo {} > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor".
            format(governor))
        adb.command(
                "echo {} > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor".
                    format(governor))

    def get_min_freq(self, cpu):
        adb = ADBInterface()

        return adb.command(
            "cat /sys/devices/system/cpu/cpu{}/cpufreq/scaling_min_freq".
            format(cpu)).split()[0]

    def get_max_freq(self, cpu):
        adb = ADBInterface()

        return adb.command(
            "cat /sys/devices/system/cpu/cpu{}/cpufreq/scaling_max_freq".
            format(cpu)).split()[0]

    def set_min_freq(self, cpu, freq):
        adb = ADBInterface()

        adb.command(
            "echo {} > /sys/devices/system/cpu/cpu{}/cpufreq/scaling_min_freq".
            format(freq, cpu))

    def set_max_freq(self, cpu, freq):
        adb = ADBInterface()

        adb.command(
            "echo {} > /sys/devices/system/cpu/cpu{}/cpufreq/scaling_max_freq".
            format(freq, cpu))

    def reset_cpu_frequencies(self, cpu):
        adb = ADBInterface()

        table_path = "/sys/devices/system/cpu/cpufreq/mp-cpufreq/{}_freq_table".format(
            self.little_name if cpu <= 3 else self.big_name)
        freqs = adb.command("cat {}".format(table_path)).split()
        min_freq = freqs[-1]
        max_freq = freqs[0]

        self.set_min_freq(cpu, min_freq)
        self.set_max_freq(cpu, max_freq)
