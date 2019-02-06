import logging
import os
import sys
import re
from pid import PID


class PIDtracer:

    def __init__(self, adb_device, name):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("PID tracer created")

        self.adb_device = adb_device
        self.name = name
        self.mainPID = self.findMainPID()
        self.allPID = []
        self.findAllPID()

    def __del__(self):
        self.logger.debug("PID tracer closed")

    def getPIDStrings(self):
        strings = []
        for x, pid in enumerate(self.allPID):
            strings.append(str(pid.pid))
        return strings

    def findMainPID(self):
        res = self.adb_device.runCommand("ps | grep " + self.name)
        if res == "":
            self.logger.error("No process running matching given process name")
            sys.exit('Need valid application name')
        pid = int(re.findall(" +(\d+) +\d+ +\d+", res)[0])
        user = int(self.adb_device.runCommand("id -u "
            + re.findall("^([^ ]+) +\d+", res)[0]))
        pname = re.findall("([^ ]+)$", res)[-1]
        self.logger.debug("Found main PID of " + str(pid) + " for process " + pname + " from user " + str(user))
        return PID( pid, user, pname, "main")

    def findAllPID(self):
        res = self.adb_device.runCommand("busybox ps -T | grep " + self.name)
        res = res.splitlines()
        for line in res:
            if line.isspace():
                continue
            #remove grep process
            if not re.match("^((?!grep).)*$", line):
                continue
            pid = int(re.findall("(\d+) +\d+ +\d+:\d+", line)[0])
            user = int(re.findall("\d+ +(\d+) +\d+:\d+", line)[0])
            tname = re.findall("\d+ *\d+ *\d*:\d* ?({?.*?})[^g][^r][^e][^p].*", line)[0]
            pname= re.findall("\d+ *\d+ *\d*:\d* ?{?.*?} ([^g][^r][^e][^p].*)", line)[0]

            self.allPID.append(PID(pid, user, pname, tname))
            self.logger.debug("Found thread " + tname + " with PID: " + str(pid))
