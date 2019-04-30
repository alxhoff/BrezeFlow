import argparse
import os
import re
import time

from ADBInterface import ADBInterface
from PIDTools import PIDTool
from SysLoggerInterface import SysLogger
from SystemMetrics import SystemMetrics
from TraceCMDParser import TracecmdProcessor
from TraceProcessor import TraceProcessor

parser = argparse.ArgumentParser()

parser.add_argument("-a", "--app", required=True,
                    help="Specifies the name of the game to be traced")
parser.add_argument("-d", "--duration", required=True, type=float,
                    help="The duration to trace")
parser.add_argument("-e", "--events", required=True,
                    help="Events that are to be traced")
parser.add_argument("-s", "--skip-clear", action='store_true',
                    help="Skip clearing trace settings")
parser.add_argument("-g", "--draw", action='store_true',
                    help="Enables the drawing of the generated graph")
parser.add_argument("-te", "--test", action='store_true',
                    help="Tests only a few hundred events to speed up testing")
parser.add_argument("-sub", "--subgraph", action='store_true',
                    help="Enable the drawing of node subgraphs")

args = parser.parse_args()


class Tracer:
    tracing_path = '/d/tracing/'

    def __init__(self, adb_device, name, functions=None, events=None,
                 trace_type="nop", duration=1, metrics=None):

        if functions is None:
            functions = []
        if events is None:
            events = []

        self.metrics = metrics
        self.adb = adb_device
        self.name = name
        self.filename = os.path.dirname(os.path.realpath(__file__)) + '/' \
            + name + "_tracer.trace"
        self.trace_type = trace_type
        self.functions = functions
        self.events = events
        self.start_time = 0
        self.duration = duration

    def run_tracer(self):

        if not args.skip_clear:
            self._clear_tracer()
            self.adb.clear_file(self.tracing_path + "set_event")
        self._set_available_events(self.events)

        self._set_available_tracer(self.trace_type)

        self._trace_for_time(self.duration)

    def _enable_tracing(self, on=True):
        if on is True:
            self.adb.write_file(self.tracing_path + "tracing_on", "1")
        else:
            self.adb.write_file(self.tracing_path + "tracing_on", "0")

    def _trace_for_time(self, duration):
        # Get timestamp when test started
        sys_time = self.adb.command("cat /proc/uptime")
        self.start_time = int(float(re.findall(r"(\d+.\d{2})", sys_time)[0]) * 1000000)

        start_time = time.time()
        self._enable_tracing(True)
        while (time.time() - start_time) < duration:
            pass

        self._enable_tracing(False)

    def get_trace_results(self):
        self.adb.pull_file("/data/local/tmp/trace.dat", self.name + ".dat")
        self.adb.pull_file("/d/tracing/trace", self.name + ".trace")

    def _get_available_events(self):
        return self.adb.read_file(self.tracing_path + "available_events")

    def _set_available_events(self, events):
        if events is None:
            return

        avail_events = self._get_available_events()

        if isinstance(events, list):
            for f in range(0, len(events)):
                if events[f] in avail_events:
                    self.adb.append_file(self.tracing_path + "set_event",
                                         events[f])
        else:
            if events in avail_events:
                self.adb.append_file(self.tracing_path + "set_event", events)

    def _set_event_filter(self, event, filter_expression):
        event_dir = self.adb.command(
            "find " + self.tracing_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb.append_file(self.tracing_path + event_dir + "/filter",
                             filter_expression)

    def _clear_event_filter(self, event):
        event_dir = self.adb.command(
            "find " + self.tracing_path + "/events -name " + event)
        if event_dir is None:
            return

        self.adb.clear_file(self.tracing_path + event_dir + "/filter")

    def _get_event_format(self, event):
        event_dir = self.adb.command(
            "find " + self.tracing_path + "/events -name " + event)
        if event_dir is None:
            return ""

        return self.adb.read_file(self.tracing_path
                                  + event_dir + "/format")

    def _get_available_tracer(self):
        return self.adb.read_file(self.tracing_path + "available_tracers")

    def _set_available_tracer(self, tracer):
        available_tracers = self._get_available_tracer()
        if tracer in available_tracers:
            self.adb.write_file(self.tracing_path
                                + "current_tracer", tracer)

    def _clear_tracer(self):
        self.adb.write_file(self.tracing_path + "current_tracer", "nop")
        self.adb.clear_file(self.tracing_path + "trace")


def main():
    adb = ADBInterface()
    pid_tool = PIDTool(adb, args.app)
    race_processor = TraceProcessor(pid_tool, args.app)
    sys_metrics = SystemMetrics(adb)

    print "Creating tracer, starting sys_logger and running trace"

    tracer = Tracer(adb,
                    args.app,
                    metrics=sys_metrics,
                    events=args.events.split(','),
                    duration=args.duration
                    )

    sys_logger = SysLogger(adb)
    sys_logger.start()
    tracer.run_tracer()
    sys_logger.stop()
    tracer.get_trace_results()

    print "Loading tracecmd data and processing"

    dat_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.app + ".dat")

    tc_processor = TracecmdProcessor(dat_path)
    tc_processor.print_event_count()
    race_processor.process_trace(sys_metrics, tc_processor, args.duration, args.draw, args.test, args.subgraph)


if __name__ == '__main__':
    main()
