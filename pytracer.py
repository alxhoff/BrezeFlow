# EXAMPLE USE
# pytracer.py -g hillclimb -d 1 -e binder_transaction,cpu_idle,sched_switch,
# cpu_frequency,update_cpu_metric,mali_utilization_stats -f output -t


import argparse
import re
import time

from tracecmd_processor import TracecmdProcessor
from adbinterface import *
from metrics import *
from pidtrace import PIDtracer
from traceprocessor import TraceProcessor

parser = argparse.ArgumentParser()

parser.add_argument("-a", "--app", required=True, type=str,
                    help="Specifies the name of the game to be traced")
parser.add_argument("-d", "--duration", required=True, type=float,
                    help="The duration to trace")
parser.add_argument("-f", "--filename", type=str, default="output",
                    help="Specify the name of the output trace file")
parser.add_argument("-e", "--events", required=True, type=str,
                    help="Events that are to be traced")
parser.add_argument("-p", "--processor", action='store_true',
                    help="If the tool should just process and not trace")
parser.add_argument("-t", "--trace", action='store_true',
                    help="Only traces, does not process trace")
parser.add_argument("-s", "--skip", action='store_true',
                    help="Skip clearing trace settings")
parser.add_argument("-m", "--multi", action='store_true',
                    help="Enables multicore processing of regex expressions")
parser.add_argument("-g", "--graph", action='store_true',
                    help="Enables the drawing of the generated graph")
parser.add_argument("-u", "--manual", action='store_true',
                    help="If set then tracing will need to be stopped manually")
parser.add_argument("-c", "--tracecmd", type=str,
                    help="Opts to parse the give tracecmd binary over regex parsing ftrace logs(faster)")

args = parser.parse_args()


class Tracer:
    ftrace_path = '/d/tracing/'

    def __init__(self, adb_device, name, functions=[], events=[],
                 trace_type="nop", duration=1, PID_filter=None, metrics=None):
        logging.basicConfig(filename="pytracer.log",
                            format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.metrics = metrics
        self.adb_device = adb_device
        self.name = name
        self.filename = op.dirname(op.realpath(__file__)) + '/' \
                        + name + "_tracer.trace"
        self.trace_type = trace_type
        self.functions = functions
        self.events = events
        self.duration = duration
        self.logger.debug("Tracer " + name + " created")
        self.PID_filter = PID_filter

    def __del__(self):
        self.logger.debug("Tracer " + self.name + " cleaned up")

    ###  ENABLING/DISABLING  ###
    def setTracing(self, on=True):
        if on == True:
            self.adb_device.write_to_file(self.ftrace_path + "tracing_on", "1")
            self.logger.debug('Tracing enabled')
        else:
            self.adb_device.write_to_file(self.ftrace_path + "tracing_on", "0")
            self.logger.debug('Tracing disabled')

    def traceForTime(self, duration, temps, manual):
        start_time = time.time()
        self.setTracing(True)
        while (time.time() - start_time) < duration:
            # log timestamp and temps
            sys_time = adbInterface.current_interface.run_command("cat /proc/uptime")
            sys_temp = adbInterface.current_interface.run_command("cat /sys/devices/10060000.tmu/temp")
            sys_time = int(float(re.findall("(\d+.\d{2})", sys_time)[0]) * 1000000)
            sys_temps = re.findall("sensor[0-4] : (\d+)", sys_temp)
            temps.append(TempLogEntry(sys_time, int(sys_temps[0]) / 1000, int(sys_temps[1]) / 1000,
                                      int(sys_temps[2]) / 1000, int(sys_temps[3]) / 1000,
                                      int(sys_temps[4]) / 1000))
        if not manual:
            self.setTracing(False)
        self.logger.debug("Trace finished after " + str(duration) + " seconds")

    ###  RESULTS  ###
    def getTraceResults(self):
        out_file = open(self.filename, "w+")
        out_file.write(self.adb_device.read_from_file(self.ftrace_path + "trace"))
        out_file.close()
        self.logger.debug("Trace results written to file " + self.filename)

    def getBinderLogs(self):
        binder_log = open("binder_transactions.log", "w+")
        binder_log.write(self.adb_device.read_from_file("/d/binder/transaction_log"))
        binder_log.close()
        self.logger.debug("Binder transactions log pulled")

    ###  FUNCTION TRACING  ###
    def _getFilterFunctions(self):
        return self.adb_device.read_from_file(self.ftrace_path +
                                              "available_filter_functions")

    def setFilterFunction(self, functions):
        if functions == []:
            return

        avail_functions = self._getFilterFunctions()

        if (isinstance(functions, list)):
            for f in range(0, len(functions)):
                self.logger.debug("Checking function '" + functions[f]
                                  + "' is valid")
                if functions[f] in avail_functions:
                    self.adb_device.append_to_file(self.ftrace_path
                                                   + "set_ftrace_filter", functions[f])
                    self.logger.debug('Appended function filter: ' + functions[f])
        else:
            self.logger.debug("Checking function '" + functions + "' is valid")
            if functions in avail_functions:
                self.adb_device.append_to_file(self.ftrace_path
                                               + "set_ftrace_filter", functions)
                self.logger.debug('Appended function filter: ' + functions)

    ### EVENT TRACING ###
    def _getAvailableEvents(self):
        return self.adb_device.read_from_file(self.ftrace_path + "available_events")

    def setAvailableEvent(self, events):
        if events == []:
            return

        avail_events = self._getAvailableEvents()

        if (isinstance(events, list)):
            for f in range(0, len(events)):
                if events[f] in avail_events:
                    self.adb_device.append_to_file(self.ftrace_path + "set_event",
                                                   events[f])
                    self.logger.debug("Appended valid event: " + events[f])
                else:
                    self.logger.debug("Event: " + events[f] + " is invalid")
        else:
            if events in avail_events:
                self.adb_device.append_to_file(self.ftrace_path + "set_event", events)
                self.logger.debug("Appended valid event: " + events)
            else:
                self.logger.debug("Event: " + events + " is invalid")

    def setEventFilter(self, event, filter_expression):
        event_dir = self.adb_device.run_command(
            "find " + self.ftrace_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb_device.append_to_file(self.ftrace_path + event_dir + "/filter",
                                       filter_expression)
        self.logger.debug("Adding filter: '" + filter_expression
                          + "' to event '" + event)

    def clearEventFilter(self, event):
        event_dir = self.adb_device.run_command(
            "find " + self.ftrace_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb_device.clear_file(self.ftrace_path + event_dir + "/filter")
        self.logger.debug("Clered filter for '" + event + "'")

    def getEventFormat(self, event):
        event_dir = self.adb_device.run_command(
            "find " + self.ftrace_path + "/events -name " + event)
        if event_dir is None:
            return ""

        return self.adb_device.read_from_file(self.ftrace_path
                                              + event_dir + "/format")

    ###  PID FILTERING  ###
    def clearFilterPID(self):
        self.adb_device.clear_file(self.ftrace_path + "set_ftrace_pid")
        self.logger.debug("PID filter cleared")

    def setFilterPID(self, PIDs):
        self.clearFilterPID()
        PID_strings = PIDs.get_app_PID_strings()
        PID_strings += PIDs.get_binder_PID_strings()
        for PID in PID_strings:
            self.adb_device.append_to_file(self.ftrace_path + "set_ftrace_pid", PID)
            self.logger.debug("Filtering PID: " + PID)

    ##  TRACER TYPES  ###
    def getAvailableTracer(self):
        return self.adb_device.read_from_file(self.ftrace_path + "available_tracers")

    def setAvailableTracer(self, tracer):
        available_tracers = self.getAvailableTracer();
        if tracer in available_tracers:
            self.adb_device.write_to_file(self.ftrace_path
                                          + "current_tracer", tracer)
            self.logger.debug("Current tracer set to " + tracer)

    def clearTracer(self):
        self.adb_device.write_to_file(self.ftrace_path + "current_tracer", "nop")
        self.logger.debug("Current tracer cleared (set to nop)")
        self.adb_device.clear_file(self.ftrace_path + "trace")
        self.logger.debug("Trace output file cleared")

    def runTracer(self, manual):
        self.logger.debug("Running tracer: " + self.name)
        if not args.skip:
            self.clearTracer()
        # set trace type
        if not args.skip:
            self.setAvailableTracer(self.trace_type)

        # set filters
        # functions
        if not args.skip:
            self.adb_device.clear_file(self.ftrace_path + "set_ftrace_filter")
        self.setFilterFunction(self.functions)

        # events
        if not args.skip:
            self.adb_device.clear_file(self.ftrace_path + "set_event")
        self.setAvailableEvent(self.events)

        # PID
        # if self.PID_filter is not None:
        #     self.setFilterPID(self.PID_filter)

        # run
        self.traceForTime(self.duration, self.metrics.temps, manual)
        SystemMetrics.current_metrics.save_temps()

        # get results
        self.getBinderLogs()
        self.getTraceResults()
        self.logger.debug("Tracer " + self.name + " finished running")


def main():
    adbBridge = adbInterface()
    PIDt = PIDtracer(adbBridge, args.app)
    tp = TraceProcessor(PIDt, args.filename)

    sys_metrics = SystemMetrics(adbBridge, args.filename)

    # Sys metrics needds to be fixed for offline processing (saving metrics)

    if args.processor is True or args.tracecmd is not None:
        sys_metrics.load_from_file(args.filename)
        if args.tracecmd:
            print "Loading tracecmd data and processing"
            TCProcessor = TracecmdProcessor(args.tracecmd)
            TCProcessor.print_event_count()
            tp.process_tracecmd(sys_metrics, args.multi, args.graph, TCProcessor)
        else:
            print "Loading trace data from file and processing"
            tp.process_trace_file(args.filename + "_tracer.trace", sys_metrics, args.multi, args.graph)
    else:
        print "Creating tracer and running"
        tracer = Tracer(adbBridge,
                        args.filename,
                        PID_filter=PIDt,
                        metrics=sys_metrics,
                        events=args.events.split(','),
                        duration=args.duration
                        )
        tracer.runTracer(args.manual)
        if args.trace is True:
            "Processing trace"
            tp.process_tracer(tracer, args.multi, args.graph)
        else:
            print "Skipping processing of trace"

if __name__ == '__main__':
    main()
