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


class GovernorController:
    available_governors = []

    def __init__(self, adb):
        self.adb = adb

    def get_governors(self):
        return self.adb.command("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors").split()

    def get_current_governor(self):
        return self.adb.command("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").split()[0]

    def set_governor(self, governor):
        self.adb.command("echo {} > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor".format(governor))
