import argparse
import os

from adbinterface import *
from metrics import *
from pidtrace import PIDtracer
from tracecmd_processor import TracecmdProcessor
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
parser.add_argument("-s", "--skip-clear", action='store_true',
                    help="Skip clearing trace settings")
parser.add_argument("-g", "--draw", action='store_true',
                    help="Enables the drawing of the generated graph")
parser.add_argument("-u", "--manual-stop", action='store_true',
                    help="If set then tracing will need to be stopped manually")
parser.add_argument("-te", "--test", action='store_true',
                    help="Tests only a few hundred events to speed up testing")
parser.add_argument("-sub", "--subgraph", action='store_true',
                    help="Enable the drawing of node subgraphs")

args = parser.parse_args()


class Tracer:
    ftrace_path = '/d/tracing/'

    def __init__(self, adb_device, name, functions=[], events=[],
                 trace_type="nop", duration=1, metrics=None):

        self.metrics = metrics
        self.adb_device = adb_device
        self.name = name
        self.filename = op.dirname(op.realpath(__file__)) + '/' \
                        + name + "_tracer.trace"
        self.trace_type = trace_type
        self.functions = functions
        self.events = events
        self.duration = duration

    def setTracing(self, on=True):
        if on is True:
            self.adb_device.write_to_file(self.ftrace_path + "tracing_on", "1")
        else:
            self.adb_device.write_to_file(self.ftrace_path + "tracing_on", "0")

    def traceForTime(self, duration, manual):
        start_time = time.time()
        self.setTracing(True)
        while (time.time() - start_time) < duration:
            pass

        if not manual:
            self.setTracing(False)

    def getTraceResults(self):
        self.adb_device.pull_file("/data/local/tmp/trace.dat", self.name + ".dat")
        # out_file = open(self.filename, "w+")
        # out_file.write(self.adb_device.read_from_file(self.ftrace_path + "trace"))
        # out_file.close()

    def _getAvailableEvents(self):
        return self.adb_device.read_from_file(self.ftrace_path + "available_events")

    def setAvailableEvent(self, events):
        if events == []:
            return

        avail_events = self._getAvailableEvents()

        if isinstance(events, list):
            for f in range(0, len(events)):
                if events[f] in avail_events:
                    self.adb_device.append_to_file(self.ftrace_path + "set_event",
                                                   events[f])
        else:
            if events in avail_events:
                self.adb_device.append_to_file(self.ftrace_path + "set_event", events)

    def setEventFilter(self, event, filter_expression):
        event_dir = self.adb_device.run_command(
            "find " + self.ftrace_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb_device.append_to_file(self.ftrace_path + event_dir + "/filter",
                                       filter_expression)

    def clearEventFilter(self, event):
        event_dir = self.adb_device.run_command(
            "find " + self.ftrace_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb_device.clear_file(self.ftrace_path + event_dir + "/filter")

    def getEventFormat(self, event):
        event_dir = self.adb_device.run_command(
            "find " + self.ftrace_path + "/events -name " + event)
        if event_dir is None:
            return ""

        return self.adb_device.read_from_file(self.ftrace_path
                                              + event_dir + "/format")

    def getAvailableTracer(self):
        return self.adb_device.read_from_file(self.ftrace_path + "available_tracers")

    def setAvailableTracer(self, tracer):
        available_tracers = self.getAvailableTracer()
        if tracer in available_tracers:
            self.adb_device.write_to_file(self.ftrace_path
                                          + "current_tracer", tracer)

    def clearTracer(self):
        self.adb_device.write_to_file(self.ftrace_path + "current_tracer", "nop")
        self.adb_device.clear_file(self.ftrace_path + "trace")

    def runTracer(self, manual):

        if not args.skip_clear:
            self.clearTracer()
            self.adb_device.clear_file(self.ftrace_path + "set_event")
        self.setAvailableEvent(self.events)

        self.setAvailableTracer(self.trace_type)

        self.traceForTime(self.duration, manual)

        self.getTraceResults()


def main():
    adb = adbInterface()
    pidtracer = PIDtracer(adb, args.app)
    tp = TraceProcessor(pidtracer, args.filename)
    sys_metrics = SystemMetrics(adb, args.filename)

    if args.processor is not True:
        print "Creating tracer and running"

        tracer = Tracer(adb,
                        args.filename,
                        metrics=sys_metrics,
                        events=args.events.split(','),
                        duration=args.duration
                        )
        tracer.runTracer(args.manual_stop)
    if args.trace is not True:
        print "Loading tracecmd data and processing"

        sys_metrics.load_from_file(args.filename)

        dat_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.app + ".dat")

        TCProcessor = TracecmdProcessor(dat_path)
        TCProcessor.print_event_count()
        tp.process_trace(sys_metrics, args.draw, TCProcessor, args.test, args.subgraph)


if __name__ == '__main__':
    main()
