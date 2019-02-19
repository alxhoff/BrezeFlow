import logging
import os.path as op

from adb import adb_commands
from adb import sign_m2crypto

class adbInterface:

    current_interface = None

    def __init__(self):
        #logger
        logging.basicConfig(filename="pytracer.log",
            format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)

        #ADB connection
        signer = sign_m2crypto.M2CryptoSigner(op.expanduser('~/.android/adbkey'))
        self.device = adb_commands.AdbCommands()
        self.device.ConnectDevice(rsa_keys=[signer])
        self.logger.debug("ADB interface created")
        adbInterface.current_interface = self

        #traces
        self.tracers = []

    def __del__(self):
        self.logger.debug("ADB interface closed")

    def runCommand(self, command):
        self.logger.debug(command)
        return self.device.Shell(command)

    def writeToFile(self, filename, contents):
        command = 'echo ' + contents + ' > ' + filename
        self.device.Shell(command)

    def clearFile(self, filename):
        self.writeToFile(filename, "")
        self.logger.debug("File " + filename + " cleared")

    def appendToFile(self, filename, contents):
        command = 'echo ' + contents + ' >> ' + filename
        self.device.Shell(command)

    def readFromFile(self, filename):
        return self.device.Pull(filename)
