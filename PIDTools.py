#!/usr/bin/env python

import re
import sys

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class PID:
    """ A process identified on a Linux system. Identified by a process and thread name as well as a unique
    identifying numeric ID.
    """

    def __init__(self, pid, pname, tname):
        self.pid = pid
        self.pname = pname
        self.tname = tname


class PIDTool:
    """ Probes the target system using ps and grep to extract all relevant threads to bother the target
    application, system services and binder threads.
    """

    def __init__(self, adb_device, name):

        self.adb_device = adb_device
        self.name = name
        main_pid = self._find_main_pid()
        self.app_pids = dict()
        self.app_pids[main_pid.pid] = main_pid
        self.app_pids[0] = PID(0, "idle_proc", "idle_thread")
        self.system_pids = dict()
        self.binder_pids = dict()

        self._find_all_pid()

    def _find_all_pid(self):

        self._find_main_pid()
        self._find_all_app_pids()
        self._find_system_server_pids()
        self._find_binder_pids()

    def _find_main_pid(self):
        """ Will find the parent PID of the target application.

        :return: PID object of the main process for the target application
        """

        res = self.adb_device.command("ps | grep " + self.name)
        if res == "":
            sys.exit('Need valid application name')

        regex_line = re.findall(r" +(\d+) +\d+ +\d+ .+ ([^ ]+)$", res)
        pid = int(regex_line[0][0])
        pname = regex_line[0][1]

        return PID(pid, pname, "main")

    def _find_system_server_pids(self):
        """ As Android applications rely heavily on the existing system services to perform portions of the
        application's execution, system services must also be taken into consideration when tracking the
        processes/threads that are responsible for a target application's execution.

        System services are found by looking for binaries that originate from the /system/bin directory.

        :return:
        """
        res = self.adb_device.command("busybox ps -T | grep /system/bin")
        res = res.splitlines()

        for line in res:
            if re.search("(Binder)", line):
                continue
            if line.isspace():
                continue
            if re.search("(grep)", line):
                continue

            regex_line = re.findall(r"(\d+) \d+ +\d+:\d+ ?({(.*)})? (.+)", line)
            pid = int(regex_line[0][0])
            if regex_line[0][1] == "":
                tname = pname = regex_line[0][3]
            else:
                tname = regex_line[0][2]
                pname = regex_line[0][3]

            self.system_pids[pid] = PID(pid, pname, tname)

    def _find_binder_pids(self):
        """ Finds the PIDs of all binder threads on the system. All binder threads are tracked as it is hard
        to know which binder threads and which parent services will be used during the execution of the target
        application.

        :return: A list of all binder PIDs
        """
        # Get all processes except the system_server itself
        res = self.adb_device.command("busybox ps -T | grep {Binder:")
        res = res.splitlines()

        for line in res:
            if line.isspace():
                continue
            if re.search("(grep)", line):
                continue

            regex_line = re.findall(r"(\d+) \d+ +\d+:\d+ {(Binder:(\d+)_.+)} (.+)", line)
            pid = int(regex_line[0][0])
            tname = regex_line[0][1]
            pname = regex_line[0][3]

            self.binder_pids[pid] = PID(pid, pname, tname)

            # Check that parent threads are in system server threads. This catches threads
            # such as the media codec which is commonly used but is not a system service
            parent_pid = int(regex_line[0][2])

            if not any(proc == parent_pid for proc in self.system_pids.keys()):
                parent_thread = self.adb_device.command("busybox ps -T | grep " + str(parent_pid))
                parent_thread = parent_thread.splitlines()
                for l in parent_thread:
                    if re.search("(Binder)", l):
                        continue
                    if line.isspace():
                        continue
                    if re.search("(grep)", l):
                        continue

                    regex_line = re.findall(r"(\d+) \d+ +\d+:\d+ ({(.*)}.* )?(.+)$", l)
                    pid = int(regex_line[0][0])
                    pname = regex_line[0][3]
                    if not regex_line[0][2]:
                        tname = pname
                    else:
                        tname = regex_line[0][2]

                    self.binder_pids[pid] = PID(pid, pname, tname)

    def _find_all_app_pids(self):
        """ Finds all child processes that are involved in the execution of the target application
        returning their PIDs. Does not include binder threads.

        :return: List of all PIDs that are using by the target applications in its execution
        """

        res = self.adb_device.command("busybox ps -T | grep " + self.name)
        res = res.splitlines()

        for line in res:
            if re.search("(Binder)", line):
                continue
            if line.isspace():
                continue
            # remove grep process
            if re.search("(grep)", line):
                continue

            regex_line = re.findall(r"(\d+) \d+ +\d+:\d+ ({(.*)}.* )?(.+)$", line)

            pid = int(regex_line[0][0])
            pname = regex_line[0][3]
            if not regex_line[0][2]:
                tname = pname
            else:
                tname = regex_line[0][2]

            self.app_pids[pid] = PID(pid, pname, tname)

    def find_child_binder_threads(self, pid):
        """ Binder threads are currently addressed using that parent binder process as the target. This can
        be seen in ASCII trace logs as the following.

        binder_transaction:   transaction=192188633 dest_node=192179164 dest_proc=3078 dest_thread=0

        Here the parent binder thread 3078 is targeted. As the thread is not specifically specified the
        binder thread that could carry out the second half of the transaction could be any one of the child
        binder threads. A list of child binder threads is found and attached to the first half of each binder
        transaction so that they can be checked against when connecting a second half with an appropriate
        first half.

        :param pid: PID whose child threads should be found
        :return: A list of all child binder PIDs
        """

        res = self.adb_device.command("busybox ps -T | grep Binder | grep " + str(pid))
        res = res.splitlines()

        child_pids = []
        for line in res:
            if line.isspace():
                continue
            child_pids.append(int(re.findall(r" *(\d+)", line)[0]))
        return child_pids

    def is_relevant_pid(self, pid):
        """ Only PIDs that appear in either the main application PIDs, binder thread PIDs and the system
        services' PIDs are considered.

        :param pid: PID that is to be checked or relevance
        :return: Boolean that signifies if the given PID is relevant
        """
        if pid in self.app_pids:
            return True
        if pid in self.system_pids:
            return True
        if pid in self.binder_pids:
            return True
        return False
