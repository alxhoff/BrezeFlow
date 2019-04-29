# Alex Hoffman 2019

import os.path as op

from adb import adb_commands
from adb import sign_m2crypto


class ADBInterface:
    current_interface = None

    def __init__(self):
        # ADB connection
        signer = sign_m2crypto.M2CryptoSigner(op.expanduser('~/.android/adbkey'))
        self.device = adb_commands.AdbCommands()
        self.device.ConnectDevice(rsa_keys=[signer])
        ADBInterface.current_interface = self

        # traces
        self.tracers = []

    def __del__(self):
        self.current_interface = None
        self.device.Close()

    def command(self, command):
        return self.device.Shell(command)

    def write_file(self, filename, contents):
        command = 'echo ' + contents + ' > ' + filename
        self.device.Shell(command)

    def clear_file(self, filename):
        self.write_file(filename, "")

    def append_file(self, filename, contents):
        command = 'echo ' + contents + ' >> ' + filename
        self.device.Shell(command)

    def read_file(self, filename):
        return self.device.Pull(filename)

    def pull_file(self, target_file, dest_filename):
        f = open(dest_filename, 'wb+')
        f.write(self.device.Pull(target_file))
        f.close()
