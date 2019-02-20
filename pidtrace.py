import logging
import re
import sys

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
        self.allAppPID.append(PID(0, "idle_proc", "idle_thread"))  # idle process
        self.allSystemPID = []
        self.allBinderPID = []
        self.findAllPID()
        self.allAppPIDStrings = self.getAppPIDStrings()
        self.allSystemPIDStrings = self.getSystemPIDStrings()
        self.allBinderPIDStrings = self.getBinderPIDStrings()
        self.allPIDStrings = self.allAppPIDStrings + self.allSystemPIDStrings + self.allBinderPIDStrings
        self.allPID = self.allAppPID + self.allSystemPID + self.allBinderPID

    def __del__(self):
        self.logger.debug("PID tracer closed")

    def getAppPIDStrings(self):
        strings = []
        for x, pid in enumerate(self.allAppPID):
            strings.append(str(pid.pid))
        return strings

    def getSystemPIDStrings(self):
        strings = []
        for x, pid in enumerate(self.allSystemPID):
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
                          + pname)
        return PID(pid, pname, "main")

    def findSystemServerPIDs(self):
        # Get all processes except the system_server itself
        res = self.adb_device.runCommand("busybox ps -T | grep /system/bin")
        res = res.splitlines()
        for line in res:
            # skip binder threads
            if re.search(".*{(Binder):.+}", line):
                continue
            if line.isspace():
                continue
            # remove grep process
            if not re.search("^((?!grep).)*$", line):
                continue
            # remove grep process
            pid = int(re.findall("^ *(\d+)", line)[0])
            pname = re.findall(".* +(.*)$", line)[0]
            tname = re.findall("\{(.*)\}", line)
            if not tname:
                tname = pname
            self.allSystemPID.append(PID(pid, pname, tname))
            self.logger.debug("Found system thread " + tname[0] + " with PID: " \
                              + str(pid))

    def findBinderPIDs(self):
        # Get all processes except the system_server itself
        res = self.adb_device.runCommand("busybox ps -T | grep {Binder:")
        res = res.splitlines()
        for line in res:
            # skip non binder threads
            if not re.search(".*{(Binder):.+}", line):
                continue
            if line.isspace():
                continue
            # remove grep process
            if "grep" in line:
                continue
            # remove grep process
            regex_find = re.findall("(\d+) \d+ +\d+:\d+ {(Binder:(\d+)_.+)} (.+)$", line)
            # pid = int(re.findall("^ *(\d+)", line)[0])
            # pname = re.findall(".* +(.*)$", line)[0]
            # tname = re.findall("\{(.*)\}", line)
            pid = int(regex_find[0][0])
            pname = regex_find[0][3]
            tname = regex_find[0][1]

            if not tname:
                tname = pname

            self.allBinderPID.append(PID(pid, pname, tname))
            self.logger.debug("Found binder thread " + tname[0] + " with PID: " \
                              + str(pid))

            # Check that parent threads are in system server threads. This catches threads
            # such as the media codec which is commonly used but is not a system service
            # parent_pid = int(re.findall("{Binder:(\d+)_.+}", line)[0])
            parent_pid = int(regex_find[0][2])
            # process will be first line as it's PID will be lower than child threads and as
            # such will be higher is list
            if not any(proc.pid == parent_pid for proc in self.allSystemPID):
                parent_thread = self.adb_device.runCommand("busybox ps -T | grep " + str(parent_pid))
                parent_thread = parent_thread.splitlines()
                for line in parent_thread:
                    if "grep" not in line:
                        pname = re.findall(".* +(.*)$", line)[0]
                        tname = re.findall("\{(.*)\}", line)
                        if not tname:
                            tname = pname
                        self.allSystemPID.append(PID(pid, pname, tname))
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
            pname = re.findall("\d+ *\d+ *\d*:\d* ?{?.*?} ([^g][^r][^e][^p].*)",
                               line)[0]

            self.allAppPID.append(PID(pid, pname, tname))
            self.logger.debug("Found thread " + tname + " with PID: " + str(pid))

    def findAllPID(self):
        self.findMainPID
        self.findAllAppPID()
        self.findSystemServerPIDs()
        self.findBinderPIDs()
