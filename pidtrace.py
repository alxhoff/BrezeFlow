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
        self.mainPID = self.find_main_PID()
        self.allAppPID = []
        self.allAppPID.append(PID(0, "idle_proc", "idle_thread"))  # idle process
        self.allSystemPID = []
        self.allBinderPID = []
        self.find_all_PID()
        self.allAppPIDStrings = self.get_app_PID_strings()
        self.allSystemPIDStrings = self.get_system_PID_strings()
        self.allBinderPIDStrings = self.get_binder_PID_strings()
        self.allPIDStrings = self.allAppPIDStrings + self.allSystemPIDStrings + self.allBinderPIDStrings
        self.allPID = self.allAppPID + self.allSystemPID + self.allBinderPID

    def __del__(self):
        self.logger.debug("PID tracer closed")

    def get_app_PID_strings(self):
        strings = []
        for x, pid in enumerate(self.allAppPID):
            strings.append(str(pid.pid))
        return strings

    def get_system_PID_strings(self):
        strings = []
        for x, pid in enumerate(self.allSystemPID):
            strings.append(str(pid.pid))
        return strings

    def get_binder_PID_strings(self):
        strings = []
        for x, pid in enumerate(self.allBinderPID):
            strings.append(str(pid.pid))
        return strings

    def get_PID_string_index(self, pid_string):
        for x, pid in enumerate(self.allPID):
            if pid.pid == pid_string:
                return x

    def find_main_PID(self):

        res = self.adb_device.run_command("ps | grep " + self.name)
        if res == "":
            self.logger.error("No process running matching given process name")
            sys.exit('Need valid application name')

        regex_line = re.findall(" +(\d+) +\d+ +\d+ .+ ([^ ]+)$", res)
        pid = int(regex_line[0][0])
        pname = regex_line[0][1]

        return PID(pid, pname, "main")

    def find_system_server_PIDs(self):
        # Get all processes except the system_server itself
        res = self.adb_device.run_command("busybox ps -T | grep /system/bin")
        res = res.splitlines()

        for line in res:
            # skip binder threads
            if re.search("(Binder)", line):
                continue
            if line.isspace():
                continue
            # skip grep process
            if re.search("(grep)", line):
                continue

            regex_line = re.findall("(\d+) \d+ +\d+:\d+ ?({(.*)})? (.+)", line)
            pid = int(regex_line[0][0])
            if regex_line[0][1] == "":
                tname = pname = regex_line[0][3]
            else:
                tname = regex_line[0][2]
                pname = regex_line[0][3]

            self.allSystemPID.append(PID(pid, pname, tname))

    def find_binder_PIDs(self):
        # Get all processes except the system_server itself
        res = self.adb_device.run_command("busybox ps -T | grep {Binder:")
        res = res.splitlines()

        for line in res:
            # skip non binder threads
            if not re.search("(Binder)", line):
                continue
            if line.isspace():
                continue
            # remove grep process
            if re.search("(grep)", line):
                continue

            regex_find = re.findall("(\d+) \d+ +\d+:\d+ {(Binder:(\d+)_.+)} (.+)", line)
            pid = int(regex_find[0][0])
            tname = regex_find[0][1]
            pname = regex_find[0][3]

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
                parent_thread = self.adb_device.run_command("busybox ps -T | grep " + str(parent_pid))
                parent_thread = parent_thread.splitlines()
                for line in parent_thread:
                    if "grep" not in line:
                        regex_find = re.findall("(\d+) \d+ +\d+:\d+ ({(.*)}.* )?(.+)$", line)
                        pid = int(regex_find[0][0])
                        pname = regex_find[0][3]
                        if not regex_find[0][2]:
                            tname = pname
                        else:
                            tname = regex_find[0][2]

                        self.allSystemPID.append(PID(pid, pname, tname))
                        self.logger.debug("Found system thread " + tname[0] + " with PID: " \
                                          + str(pid))

    def find_child_binder_threads(self, PID):

        res = self.adb_device.run_command("busybox ps -T | grep Binder | grep " + str(PID))
        res = res.splitlines()

        child_PIDs = []
        for line in res:
            if line.isspace():
                continue
            child_PIDs.append(int(re.findall(" *(\d+)", line)[0]))
        return child_PIDs

    def find_all_app_PID(self):

        res = self.adb_device.run_command("busybox ps -T | grep " + self.name)
        res = res.splitlines()

        for line in res:
            if line.isspace():
                continue
            # remove grep process
            if re.search("(grep)", line):
                continue

            regex_line = re.findall("(\d+) \d+ +\d+:\d+ {(.+)} (.+)", line)

            pid = int(regex_line[0][0])
            tname = regex_line[0][1]
            pname = regex_line[0][2]

            self.allAppPID.append(PID(pid, pname, tname))

    def find_all_PID(self):
        self.find_main_PID
        self.find_all_app_PID()
        self.find_system_server_PIDs()
        self.find_binder_PIDs()
