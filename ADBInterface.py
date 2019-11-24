#!/usr/bin/env python

import os.path as op
import re

from adb import adb_commands
from adb import sign_m2crypto

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class ADBInterface:
    """ Object to interface with an attached Android device over an ADB connection. The ADB connection
    is established using the Python ASB + Fastboot implementation from Google. For this connection to work
    the "standard" command line ADB server must not be running as this will block access to the target
    device's ADB connection.

    """

    current_interface = None

    def __init__(self):
        signer = sign_m2crypto.M2CryptoSigner(
            op.expanduser("~/.android/adbkey"))
        self.device = adb_commands.AdbCommands()
        self.device.ConnectDevice(rsa_keys=[signer])
        # ADBInterface.current_interface = self
        self.kill_media()

    def __del__(self):
        self.current_interface = None
        self.device.Close()

    def kill_media(self):
        self.kill_proc("process.media")

    # Used for a bug in Lineage OS 7.1 where the media service consumes all network memory, causing ADB errors and
    # killing the tool
    def kill_proc(self, proc):
        re_line = self.command("busybox top -n 1 | grep {}".format(proc))

        re_line.splitlines()

        regex_line = re.findall(r"([0-9]+).+process\.media", re_line)

        if len(regex_line):
            for line in regex_line:
                self.command("kill {}".format(line))
                print("killed {} proc: {}".format(proc, line))

    def command(self, command):
        """ Executes a command on the target device.

        :param command: String literal of the command that is to be run
        :return: The text output that would otherwise be displayed on stdout
        """
        return self.device.Shell(command)

    def write_file(self, filename, contents):
        """ Writes the provided string into the target file, this is done using 'echo >'.

        :param filename: File which is to be written into
        :param contents: String contents that is to be written into file
        """
        command = "echo " + contents + " > " + filename
        self.device.Shell(command)

    def clear_file(self, filename):
        """ Clears the target file using 'echo >'

        :param filename: File that is to be cleared
        """
        self.write_file(filename, "")

    def append_to_file(self, filename, contents):
        """ Appends the provided contents to the end of the target file. This is done using 'echo >>'.

        :param filename: File that is to be appended to
        :param contents: String contents that is to be appended to the target file
        """
        command = "echo " + contents + " >> " + filename
        self.device.Shell(command)

    def read_file(self, filename):
        """ Reads the contents of a target file on the target Android system.

        :param filename: File that is to be read
        :return: A string representation of the target file's contents
        """
        return self.device.Pull(filename)

    def pull_file(self, target_file, dest_filename):
        """ Pulls the target file from the target Android system into the provided file, relative to the
        working directory.

        :param target_file: File path and name of the file that is to be pulled
        :param dest_filename: File path and name, relative to working directory, where the pulled file
        should be stored
        """
        self.kill_media()
        f = open(dest_filename, "wb+")
        f.write(self.device.Pull(target_file))
        f.close()
