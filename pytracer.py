import os.path as op
import logging
import time

from adb import adb_commands
from adb import sign_m2crypto

#def adb_write_to_file(dev, filename, contents):
logging.basicConfig(filename="pytracer.log", format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug('Logger initd')

class tracer:

    ftrace_path = '/d/tracing/'

    def __init__(self, name):
        self.name = name
        signer = sign_m2crypto.M2CryptoSigner(op.expanduser('~/.android/adbkey'))
        # Connect to the device
        self.device = adb_commands.AdbCommands()
        self.device.ConnectDevice(rsa_keys=[signer])
        logger.debug('Device connected')

    def __del__(self):
        logger.debug('Trace finished')

    def writeToFile(self, filename, contents):
        command = 'echo ' + contents + ' > ' + self.ftrace_path + filename
        logger.debug(command)
        self.device.Shell(command)

    def appendToFile(self, filename, contents):
        command = 'echo ' + contents + ' >> ' + tracer.ftrace_path + filename
        logger.debug(command)
        self.device.Shell(command)

    def readFromFile(self, filename):
        return self.device.Pull(tracer.ftrace_path + filename)

    def setTracing(self, on=True):
        if on == True:
            self.writeToFile("tracing_on", "1")
            logger.debug('Tracing enabled')
        else:
            self.writeToFile("tracing_on", "0")
            logger.debug('Tracing disabled')

    def traceForTime(self, duration):
        start = time.time()
        self.setTracing(True)
        time.sleep(duration)
        self.setTracing(False)
        logger.debug("Trace finished after " + duration + " seconds")

    def getTraceResults(self, filename="results.trace"):
        full_path = op.dirname(op.realpath(__file__)) + '/' + filename
        out_file = open(full_path, "w+")
        out_file.write(self.readFromFile("trace"))
        out_file.close()
        logger.debug("Trace results written to file " + full_path)

    def getFilterFunctions(self):
        return self.readFromFile("available_filter_functions")

    def setFilterFunction(self, function):
        functions = self.getFilterFunctions()
        if function in functions:
            self.writeToFile("set_ftrace_filter", function)
            logger.debug('Filter function set to ' + function)

