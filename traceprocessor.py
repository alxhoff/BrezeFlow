import logging
from aenum import Enum
from event import *
import re
import xlsxwriter

class traceProcessor:

    def __init__(self):
        logging.basicConfig(filename="pytracer.log",
                format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Trace processor created")

    def filterTracePID(self, tracer, PIDt, output_filename=""):
        if output_filename == "":
            output_filename = tracer.filename + "_filtered"
        f = open(tracer.filename)
        unfiltered = f.readlines()
        filtered = []
        pids = PIDt.getPIDStrings()
        for x, line in enumerate(unfiltered): #make sure that PID isn't in time stamp
            if any((("=" + pid) or ("-" + pid)) in line for pid in pids) or x < 11:
                filtered.append(line)

        f = open(output_filename, 'w')
        f.writelines(filtered)
        self.logger.debug("Written filtered lines to: " + output_filename)
        f.close()

    def keepPIDLine(self, line, PIDt):
        pids = PIDt.getPIDStrings()

        if any(("=" + pid) or ("-" + pid) in line for pid in pids):
            return True
        return False

    def _processSchedWakeup(self, line):
        pid =  int(re.findall("-(\d+) *\[", line)[0])
        time = int(float(re.findall(" (\d+\.\d+):", line)[0]) * 1000000)
        cpu = int(re.findall(" target_cpu=(\d+)", line)[0])

        return event_wakeup(pid, time, cpu)

    def _processSchedSwitch(self, line):
        pid =  int(re.findall("-(\d+) *\[", line)[0])
        time = int(float(re.findall(" (\d+\.\d+):", line)[0]) * 1000000)
        cpu = int(re.findall(" +\[(\d+)\] +", line)[0])
        prev_state = re.findall("prev_state=([RSDx]{1})", line)[0]
        next_pid = int(re.findall("next_pid=(\d+)", line)[0])

        return event_sched_switch(pid, time, cpu, prev_state, next_pid)

    def _processSchedIdle(self, line):
        time = int(float(re.findall(" (\d+\.\d+):", line)[0]) * 1000000)
        cpu = int(re.findall(" +\[(\d+)\] +", line)[0])
        state = int(re.findall("state=(\d+)", line)[0])

        return event_idle(time, cpu, state)

    def _processSchedFreq(self, line):
        pid =  int(re.findall("-(\d+) *\[", line)[0])
        time = int(float(re.findall(" (\d+\.\d+):", line)[0]) * 1000000)
        cpu = int(re.findall(" +\[(\d+)\] +", line)[0])
        freq = int(re.findall("freq: (\d+) ", line)[0])
        load = int(re.findall(" load: (\d+)", line)[0])

        return event_freq_change(pid, time, freq, load, cpu)

    def processTrace(self, tracer, PIDt):
        #open trace
        try:
            f = open(tracer.filename, "r")
            self.logger.debug("Tracer " + tracer.filename + " opened for \
                    processing ")
        except IOError:
            self.logger.error("Could not open trace file" + tracer.filename)
            sys.exit("Tracer unable to be opened for processing")
        raw_lines = []
        raw_lines = f.readlines()
        processed_events = []
        #determine tracer type
        self.logger.debug("Trace contains " + str(len(raw_lines)) + " lines")
        for line in raw_lines[11:]:
            if not self.keepPIDLine(line, PIDt):
                continue
            if "sched_wakeup" in line:
                processed_events.append(self._processSchedWakeup(line))
                self.logger.debug("Wakeup event line: " + line)
            elif "sched_switch" in line:
                processed_events.append(self._processSchedSwitch(line))
                self.logger.debug("Sched switch: " + line)
            elif "cpu_idle" in line:
                processed_events.append(self._processSchedIdle(line))
                self.logger.debug("Idle event line: " + line)
            elif "update_cpu_metric" in line:
                processed_events.append(self._processSchedFreq(line))
                self.logger.debug("Freq event line: " + line)

        if processed_events == []:
            self.logger.debug("Processing trace failed")
            sys.exit("Processing trace failed")

        #write events into excel file
        start_time = processed_events[0].time

        output_workbook = xlsxwriter.Workbook(tracer.name + "_events.xlsx")
        output_worksheet = output_workbook.add_worksheet()

        time_col = 0
        cpu_col = 1
        PID_col = 2

        prev_state_col = 3
        next_pid_col = 4

        freq_freq_col = 5
        freq_load_col = 6

        idle_state_col = 7

        wake_event_col = 8

        output_worksheet.write_string(0, time_col, "Time")
        output_worksheet.write_string(0, cpu_col, "CPU")
        output_worksheet.write_string(0, PID_col, "PID")
        output_worksheet.write_string(0, prev_state_col, "Prev State")
        output_worksheet.write_string(0, next_pid_col, "Next PID")
        output_worksheet.write_string(0, freq_freq_col, "Frequency Change")
        output_worksheet.write_string(0, freq_load_col, "Load")
        output_worksheet.write_string(0, idle_state_col, "Idle")
        output_worksheet.write_string(0, wake_event_col, "Wake Event")

        for event in processed_events:
            if isinstance(event, event_wakeup):
                output_worksheet.write_number(event.time - start_time + 1,
                        time_col, event.time - start_time + 1)
                output_worksheet.write_number(event.time - start_time + 1,
                        PID_col, event.PID)
                output_worksheet.write_number(event.time - start_time + 1,
                        cpu_col, event.cpu)
                output_worksheet.write_string(event.time - start_time + 1,
                        wake_event_col, "X")
                self.logger.debug("Wakeup event added to row: " +
                        str(event.time - start_time + 1))

            elif isinstance(event, event_sched_switch):
                output_worksheet.write_number(event.time - start_time + 1,
                        time_col, event.time - start_time + 1)
                output_worksheet.write_number(event.time - start_time + 1,
                        PID_col, event.PID)
                output_worksheet.write_number(event.time - start_time + 1,
                        cpu_col, event.cpu)
                output_worksheet.write_string(event.time - start_time + 1,
                        prev_state_col, event.prev_state)
                output_worksheet.write_number(event.time - start_time + 1,
                        next_pid_col, event.next_pid)

                self.logger.debug("Switch event added to row: " +
                        str(event.time - start_time + 1))

            elif isinstance(event, event_freq_change):
                output_worksheet.write_number(event.time - start_time + 1,
                        time_col, event.time - start_time + 1)
                output_worksheet.write_number(event.time - start_time + 1,
                        freq_freq_col, event.freq)
                output_worksheet.write_number(event.time - start_time + 1,
                        freq_load_col, event.load)
                output_worksheet.write_number(event.time - start_time + 1,
                        cpu_col, event.cpu)
                self.logger.debug("Freq event added to row: " +
                        str(event.time - start_time + 1))
            elif isinstance(event, event_idle):
                output_worksheet.write_number(event.time - start_time + 1,
                        time_col, event.time - start_time + 1)
                output_worksheet.write_number(event.time - start_time + 1,
                        cpu_col, event.cpu)
                output_worksheet.write_number(event.time - start_time + 1,
                        idle_state_col, event.state)
                self.logger.debug("Idle event added to row: " +
                        str(event.time - start_time + 1))
            else:
                self.logger.debug("Unknown event")

        output_workbook.close()