import logging
import os.path as op

from adb import adb_commands
from adb import sign_m2crypto

from pytracer import tracer
from pid_trace import PIDtracer

class adbInterface:

    def __init__(self):
        #logger
        logging.basicConfig(filename="pytracer.log", format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)

        #ADB connection
        signer = sign_m2crypto.M2CryptoSigner(op.expanduser('~/.android/adbkey'))
        self.device = adb_commands.AdbCommands()
        self.device.ConnectDevice(rsa_keys=[signer])
        self.logger.debug("ADB interface created")

        #traces
        self.tracers = []

    def __del__(self):
        self.logger.debug("ADB interface closed")

    def createTracer(self, name, function="none", trace_type="function", duration=1):
        new_trace = tracer(self, name, function, trace_type, duration)
        self.tracers.append(new_trace)

    def createPIDtool(self, name):
        self.PIDtool = PIDtracer(self, name)

    def runCommand(self, command):
        return self.device.Shell(command)

    def writeToFile(self, filename, contents):
        command = 'echo ' + contents + ' > ' + filename
        self.device.Shell(command)
        self.logger.debug(command)

    def clearFile(self, filename):
        self.writeToFile(filename, "")
        self.logger.debug("File " + filename + " cleared")

    def appendToFile(self, filename, contents):
        command = 'echo ' + contents + ' >> ' + filename
        self.device.Shell(command)
        self.logger.debug(command)

    def readFromFile(self, filename):
        return self.device.Pull(filename)

    def runTracers(self):
        for tracer in self.tracers:
            tracer.run()
