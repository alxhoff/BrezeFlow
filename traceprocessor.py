import logging
from aenum import Enum
from event import *

class traceType(Enum):
    UNKNOWN             = 0
    SCHED_WAKEUP        = 1
    SCHED_SWITCH        = 2
    SCHED_FREQ          = 3
    SCHED_IDLE          = 4

class traceProcessor:

    def __init__(self):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Trace processor created")

    def filterTracePID(self, tracer, PIDtracer, output_filename=""):
        if output_filename == "":
            output_filename = tracer.filename + "_filtered"
        f = open(tracer.filename)
        unfiltered = f.readlines()
        filtered = []
        pids = PIDtracer.getPIDStrings()
        for x, line in enumerate(unfiltered): #make sure that PID isn't in time stamp
            if any((("=" + pid) or ("-" + pid)) in line for pid in pids) or x < 11:
                filtered.append(line)

        f = open(output_filename, 'w')
        f.writelines(filtered)
        self.logger.debug("Written filtered lines to: " + output_filename)
        f.close()

    def keepPIDLines(self, tracer_lines, PIDtracer):
        filtered = []
        pids = PIDtracer.getPIDStrings()

        for x, line in enumerate(tracer_lines, 11):
            if any(("=" + pid) or ("-" + pid) in line for pid in pids):
                filtered.append(line)

        return filtered

    def _processSchedWakeup(self, tracer_lines):
        events = []
        for x, line in enumerate(tracer_lines, 11):
            split_line = line.split()
            #get PID
            pid = split_line.split('-')[-1]
            #get time
            time = split_line[3]
            #get cpu
            for x, chunk in enumerate(split_line):
                if "target_cpu=" in chunk:
                    cpu = int(chunk[-3:-1])
                    break
            #append to known events
            events.append(even_wakeup(pid, time, cpu))

        return events

    def _processSchedSwitch(self, tracer_lines):
        events = []
        for x, line in enumerate(tracer_lines, 11):
            split_line = line.split()
            #get  PI

    def _processSchedIdle(self, tracer_lines):
        events = []
        for x, line in enumerate(tracer_lines, 11):
            if "cpu_idle" in line:
                split_line = line.split()
                #get time
                time = split_line[3]
                #get cpu
                cpu = int(split_line[6][-1])
                events.append(event_idle(time, cpu))

        return events

    def _processSchedFreq(self, tracer_lines):
        events = []
        for line in tracer_lines[11:]:
            if "update_cpu_metric" in line:
                split_line = line.split()
                print split_line
                #get PID
                pid = split_line[0].split('-')[-1]
                #get time
                time = split_line[3]
                #get freq
                freq = split_line[9]
                #get load
                load = split_line[11]
                #get cpu
                cpu = int(split_line[7])
                events.append(event_freq_change(pid, time, freq, load, cpu))

        return events

    def processTrace(self, tracer, PIDtracer):
        #open trace
        try:
            f = open(tracer.filename, "r")
            self.logger.debug("Tracer " + tracer.filename + " opened for \
                    processing ")
        except IOError:
            self.logger.error("Could not open trace file" + tracer.filename)
            sys.exit("Tracer unable to be opened for processing")

        raw_lines = f.readlines()
        processed_events = []
        trace_type = traceType.UNKNOWN
        #determine tracer type
        for x, line in enumerate(raw_lines, 11):
            if "shed_wakeup" in line:
                trace_type = traceType.SCHED_WAKEUP
                self.logger.debug("Trace " + tracer.filename + " of type wakeup")
                break
            #elif sched_switch in line:
            #    trace_type = traceType.SCHED_SWITCH
            #    self.logger.debug("Trace " + tracer.filename + " of type switch")
            #    break
            elif "cpu_idle" in line:
                trace_type = traceType.SCHED_IDLE
                self.logger.debug("Trace " + tracer.filename + " of type idle")
            elif "update_cpu_metric" in line:
                trace_type = traceType.SCHED_FREQ
                self.logger.debug("Trace " + tracer.filename + " of type freq")
                break

        #filter trace
        if trace_type == (traceType.SCHED_SWITCH or traceType.SCHED_WAKEUP):
            raw_lines = keepPIDLines(raw_lines, PIDtracer)

        #paid processing
        if trace_type == traceType.UNKNOWN:
            self.logger.debug("Trace could not be processed, unknown type")
            sys.exit("Trace type unknown, could not be processed")
        elif trace_type == traceType.SCHED_WAKEUP:
            processed_events = self._processSchedWakeup(raw_lines)
        elif trace_type == traceType.SCHED_SWITCH:
            processed_events = self._processSchedSwitch(raw_lines)
        elif trace_type == traceType.SCHED_FREQ:
            processed_events = self._processSchedFreq(raw_lines)
        elif trace_type == traceType.SCHED_IDLE:
            processed_events = self._processSchedIdle(raw_lines)

        if processed_events == []:
            self.logger.debug("Processing trace failed")
            sys.exit("Processing trace failed")

        try:
            f = open(tracer.filename, 'w')
        except IOError:
            self.logger.error("Could not write to trace file " + tracer.filename)
            sys.exit("Could not write to trace file " + tracer.filename)





