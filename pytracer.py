import logging
import time
import os.path as op

from adb import adb_commands
from adb import sign_m2crypto

#def adb_write_to_file(dev, filename, contents):

class tracer:

    ftrace_path = '/d/tracing/'

    def __init__(self, adb_device, name, function="none", trace_type="function", duration=1):
        self.adb_device = adb_device
        self.name = name
        self.trace_type = trace_type
        self.function = function
        self.duration = duration
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Tracer " + name + " created")

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
        full_path = op.dirname(op.realpath(__file__)) + '/' + filename
        out_file = open(full_path, "w+")
        out_file.write(self.adb_device.readFromFile(self.ftrace_path + "trace"))
        out_file.close()
        self.logger.debug("Trace results written to file " + full_path)

    def _getFilterFunctions(self):
        return self.adb_device.readFromFile(self.ftrace_path + "available_filter_functions")

    def setFilterFunction(self, function):
        if(function == "none"):
            return

        functions = self._getFilterFunctions()

        for f in function:
            if function in functions:
                self.adb_device.writeToFile(self.ftrace_path + "set_ftrace_filter", function)
                self.logger.debug('Filter function set to ' + function)

    def getAvailableTracer(self):
        return self.adb_device.readFromFile(self.ftrace_path + "available_tracers")

    def setAvailableTracer(self, tracer):
        available_tracers = self.getAvailableTracer();
        if tracer in available_tracers:
            self.adb_device.writeToFile(self.ftrace_path + "current_tracer", tracer)
            self.logger.debug("Current tracer set to " + tracer)

    def run(self):
        #set trace type
        self.setAvailableTracer(self.trace_type)

        #set filters
        #TODO implement filters etc

        #run
        self.traceForTime(self.duration)

        #get results
        self.getTraceResults(self.name + "_tracer.trace")
        self.logger.debug("Tracer " + self.name + " finished running")
