import logging
import time
import os.path as op

from adb import adb_commands
from adb import sign_m2crypto

#def adb_write_to_file(dev, filename, contents):

class tracer:

    ftrace_path = '/d/tracing/'

    def __init__(self, adb_device, name, functions=[],
            trace_type="function", duration=1, PID_filter=None):
        self.adb_device = adb_device
        self.name = name
        self.filename = op.dirname(op.realpath(__file__)) + '/' + name + "_tracer.trace"
        self.trace_type = trace_type
        self.functions = functions
        self.duration = duration
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Tracer " + name + " created")
        if PID_filter is not None:
            self.PID_filter = PID_filter

    def __del__(self):
        self.logger.debug("Tracer " + self.name + " cleaned up")

    def setTracing(self, on=True):
        if on == True:
            self.adb_device.writeToFile(self.ftrace_path + "tracing_on", "1")
            self.logger.debug('Tracing enabled')
        else:
            self.adb_device.writeToFile(self.ftrace_path + "tracing_on", "0")
            self.logger.debug('Tracing disabled')

    def traceForTime(self, duration):
        start = time.time()
        self.setTracing(True)
        time.sleep(duration)
        self.setTracing(False)
        self.logger.debug("Trace finished after " + str(duration) + " seconds")

    def getTraceResults(self, filename="results.trace"):
        out_file = open(self.filename, "w+")
        out_file.write(self.adb_device.readFromFile(self.ftrace_path + "trace"))
        out_file.close()
        self.logger.debug("Trace results written to file " + self.filename)

    def _getFilterFunctions(self):
        return self.adb_device.readFromFile(self.ftrace_path + "available_filter_functions")

    def setFilterFunction(self, functions):
        if(functions == []):
            return

        avail_functions = self._getFilterFunctions()

        if(isinstance(functions, list)):
            for f in range(0, len(functions)):
                self.logger.debug("Checking function '" + functions[f] + "' is valid")
                if functions[f] in avail_functions:
                    self.adb_device.appendToFile(self.ftrace_path + "set_ftrace_filter",
                        functions[f])
                    self.logger.debug('Appended function filter: ' + functions[f])
        else:
            self.logger.debug("Checking function '" + functions + "' is valid")
            if functions in avail_functions:
                self.adb_device.appendToFile(self.ftrace_path + "set_ftrace_filter",
                    functions)
                self.logger.debug('Appended function filter: ' + functions)

    def clearFilterPID(self):
        self.adb_device.clearFile(self.ftrace_path + "set_ftrace_pid")

    def setFilterPID(self, PIDs):
        self.clearFilterPID()
        for x, PID in enumerate(PIDs):
            self.adb_device.appendToFile(self.ftrace_path + "set_frace_pid", PID.pid)

    def getAvailableTracer(self):
        return self.adb_device.readFromFile(self.ftrace_path + "available_tracers")

    def setAvailableTracer(self, tracer):
        available_tracers = self.getAvailableTracer();
        if tracer in available_tracers:
            self.adb_device.writeToFile(self.ftrace_path + "current_tracer", tracer)
            self.logger.debug("Current tracer set to " + tracer)

    def run(self):
        self.logger.debug("Running tracer: " + self.name)
        #set trace type
        self.setAvailableTracer(self.trace_type)

        #set filters
        #functions
        self.adb_device.clearFile(self.ftrace_path + "set_ftrace_filter")
        self.setFilterFunction(self.functions)

        #PID
        if self.PID_filter is not None:
            self.setFilterPID(self.PID_filter)

        #run
        self.traceForTime(self.duration)

        #get results
        self.getTraceResults(self.name + "_tracer.trace")
        self.logger.debug("Tracer " + self.name + " finished running")
