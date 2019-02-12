import logging
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
        self.allAppPID = []
        self.allAppPID.append(PID(0,"idle_proc", "idle_thread"))#idle process
        self.allBinderPID = []
        self.findAllPID()
        self.allAppPIDStrings = self.getAppPIDStrings()
        self.allBinderPIDStrings = self.getBinderPIDStrings()
        self.allPIDStrings = self.allAppPIDStrings + self.allBinderPIDStrings
        self.allPID = self.allAppPID + self.allBinderPID

    def __del__(self):
        self.logger.debug("PID tracer closed")

    def getAppPIDStrings(self):
        strings = []
        for x, pid in enumerate(self.allAppPID):
            strings.append(str(pid.pid))
        return strings

    def getBinderPIDStrings(self):
        strings = []
        for x, pid in enumerate(self.allBinderPID):
            strings.append(str(pid.pid))
        return strings

    def getPIDStringIndex(self, pid_string):
        for x, pid in enumerate(self.allPID):
            if pid.pid == pid_string:
                return x

    def findMainPID(self):
        res = self.adb_device.runCommand("ps | grep " + self.name)
        if res == "":
            self.logger.error("No process running matching given process name")
            sys.exit('Need valid application name')
        pid = int(re.findall(" +(\d+) +\d+ +\d+", res)[0])
        pname = re.findall("([^ ]+)$", res)[-1]
        self.logger.debug("Found main PID of " + str(pid) + " for process "
                + pname )
        return PID( pid, pname, "main")

    def findSystemServerBinderPIDs(self):
        # Get all processes except the system_server itself
        res = self.adb_device.runCommand("busybox ps -T | grep Binder")
        res = res.splitlines()
        for line in res:
            if line.isspace():
                continue
            # remove grep process
            if not re.match("^((?!grep).)*$", line):
                continue
            # remove grep process
            pid = int(re.findall("^ *(\d+)", line)[0])
            tname = re.findall("\{(.*)\}", line)[0]
            pname = re.findall(".* +(.*)$", line)[0]
            self.allBinderPID.append(PID(pid, pname, tname))
            self.logger.debug("Found system thread " + tname[0] + " with PID: " \
                    + str(pid))

    def findChildBinderThreads(self, PID):
        res = self.adb_device.runCommand("busybox ps -T | grep Binder | grep " + \
                str(PID))
        res = res.splitlines()
        child_PIDs = []
        for line in res:
            if line.isspace():
                continue
            child_PIDs.append(int(re.findall(" *(\d+)", line)[0]))
        return child_PIDs

    def findAllAppPID(self):
        res = self.adb_device.runCommand("busybox ps -T | grep " + self.name)
        res = res.splitlines()
        for line in res:
            if line.isspace():
                continue
            # remove grep process
            if not re.match("^((?!grep).)*$", line):
                continue
            pid = int(re.findall("(\d+) +\d+ +\d+:\d+", line)[0])
            tname = re.findall("\d+ *\d+ *\d*:\d* ?({?.*?})[^g][^r][^e][^p].*",
                    line)[0]
            pname= re.findall("\d+ *\d+ *\d*:\d* ?{?.*?} ([^g][^r][^e][^p].*)",
                    line)[0]

            self.allAppPID.append(PID(pid, pname, tname))
            self.logger.debug("Found thread " + tname + " with PID: " + str(pid))

    def findAllPID(self):
        self.findMainPID
        self.findAllAppPID()
        self.findSystemServerBinderPIDs()
