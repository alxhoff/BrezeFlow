import re
import sys

import xlsxwriter

from adbinterface import *
from event import *
from grapher import *
from metrics import *

class traceProcessor:

    def __init__(self):
        logging.basicConfig(filename="pytracer.log",
                            format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Trace processor created")

    def filter_trace_PID(self, tracer, PIDt, output_filename=""):
        if output_filename == "":
            output_filename = tracer.filename + "_filtered"
        f = open(tracer.filename)
        unfiltered = f.readlines()
        filtered = []
        for x, line in enumerate(unfiltered):  # make sure that PID isn't in time stamp
            if self.keep_PID_line(line, PIDt) or x < 11:
                filtered.append(line)

        f = open(output_filename, 'w')
        f.writelines(filtered)
        self.logger.debug("Written filtered lines to: " + output_filename)
        f.close()

    def keep_PID_line(self, line, PIDt):
        pids = PIDt.allPIDStrings[1:]
        if any(re.search("-(" + str(pid) + ") +|=(" + str(pid) + ") ", line) for pid in pids):
            return True
        elif "update_cpu_metric" in line:
            return True
        elif "mali_utilization_stats" in line:
            return True
        return False

    def _process_sched_wakeup(self, line):
        pid = int(re.findall("-(\d+) *\[", line)[0])
        time = int(round(float(re.findall(" (\d+\.\d+):", line)[0]) * 1000000))
        cpu = int(re.findall(" target_cpu=(\d+)", line)[0])
        name = re.findall("^ *(.+)-\d+ +", line)[0]

        return EventWakeup(pid, time, cpu, name)

    def _process_sched_switch(self, line):
        name = re.findall("^ *(.+)-\d+ +", line)[0]

        state_next = re.findall("prev_state=([RSDx]{1})[+]? ==> next_comm=.+ next_pid=(\d+)", line)
        prev_state = state_next[0][0]
        next_pid = int(state_next[0][1])

        pid_cpu_time = re.findall("-(\d+) +\[(\d{3})\] .{4} +(\d+.\d+)", line)
        pid = int(pid_cpu_time[0][0])
        cpu = int(pid_cpu_time[0][1])
        time = int(round(float(pid_cpu_time[0][2]) * 1000000))

        return EventSchedSwitch(pid, time, cpu, name, prev_state, next_pid)

    def _process_sched_idle(self, line):
        time = int(round(float(re.findall(" (\d+\.\d+):", line)[0]) * 1000000))
        cpu = int(re.findall(" +\[(\d+)\] +", line)[0])
        name = re.findall("^ *(.+)-\d+ +", line)[0]
        state = int(re.findall("state=(\d+)", line)[0])

        return EventIdle(time, cpu, state, name)

    def _process_sched_freq(self, line):
        regex_line = re.findall("-(\d+) +\[(\d{3})\] .{4} +(\d+.\d+)", line)

        pid = int(regex_line[0][0])
        cpu = int(regex_line[0][1])
        time = int(round(float(regex_line[0][2]) * 1000000))

        regex_line = re.findall("cpu: (\d+) freq: (\d+) load: (\d+)", line)

        target_cpu = int(regex_line[0][0])
        freq = int(regex_line[0][1])
        util = int(regex_line[0][2])

        return EventFreqChange(pid, time, cpu, freq, util, target_cpu)

    def _process_binder_transaction(self, line):
        regex_line = re.findall("^ *(.*)-(\d+) +\[(\d{3})\] .{4} +(\d+.\d+)", line)

        name = regex_line[0][0]
        pid = int(regex_line[0][1])
        cpu = int(regex_line[0][2])
        time = int(round(float(regex_line[0][3]) * 1000000))

        regex_line = re.findall(
            "dest_proc=(\d+) dest_thread=(\d+) reply=(\d) flags=(0x[0-9a-f]+) code=(0x[0-9a-f]+)", line)

        to_proc = int(regex_line[0][1])
        if to_proc == 0:
            to_proc = int(regex_line[0][0])
        trans_type = int(regex_line[0][2])
        flags = int(regex_line[0][3], 16)
        code = int(regex_line[0][4], 16)

        return EventBinderCall(pid, time, cpu, name, trans_type, to_proc, flags, code)

    def _process_mali_util(self, line):
        regex_line = re.findall("-(\d+) +\[(\d{3})\] .{4} +(\d+.\d+): mali_utilization_stats: util=(\d+) norm_util=\d+ norm_freq=(\d+)",
                                line)

        pid = int(regex_line[0][0])
        cpu = int(regex_line[0][1])
        time = int(round(float(regex_line[0][2]) * 1000000))
        util = int(regex_line[0][3])
        freq = int(regex_line[0][4])

        return EventMaliUtil(pid, time, cpu, util, freq)

    def write_to_xlsx(self, processed_events, filename):
        # write events into excel file
        start_time = processed_events[0].time

        output_workbook = xlsxwriter.Workbook(filename + "_events.xlsx")
        output_worksheet = output_workbook.add_worksheet()

        time_col = 0
        event_col = 1
        cpu_col = 2
        PID_col = 3

        prev_state_col = 4
        next_pid_col = 5

        binder_type_col = 6
        binder_ID_col = 7
        binder_flags_col = 8
        binder_code_col = 9

        freq_freq_col = 10
        freq_load_col = 11

        idle_state_col = 12

        wake_pid_col = 13
        wake_event_col = 14

        output_worksheet.write_string(0, time_col, "Time")
        output_worksheet.write_string(0, event_col, "Event")
        output_worksheet.write_string(0, cpu_col, "CPU")
        output_worksheet.write_string(0, PID_col, "PID")
        output_worksheet.write_string(0, prev_state_col, "Prev State")
        output_worksheet.write_string(0, next_pid_col, "Next PID")
        output_worksheet.write_string(0, binder_type_col, "Binder Type")
        output_worksheet.write_string(0, binder_ID_col, "Binder ID")
        output_worksheet.write_string(0, binder_flags_col, "Binder Flags")
        output_worksheet.write_string(0, binder_code_col, "Binder Code")
        output_worksheet.write_string(0, freq_freq_col, "Frequency Change")
        output_worksheet.write_string(0, freq_load_col, "Load")
        output_worksheet.write_string(0, idle_state_col, "Idle")
        output_worksheet.write_string(0, wake_event_col, "Wake Event")

        start_row = 2
        for event in processed_events:
            if isinstance(event, EventWakeup):
                output_worksheet.write_number(start_row,
                                              time_col, event.time - start_time + 1)
                output_worksheet.write_string(start_row,
                                              event_col, str(JobType.WAKEUP.value))
                output_worksheet.write_number(start_row,
                                              PID_col, event.PID)
                output_worksheet.write_number(start_row,
                                              cpu_col, event.cpu)
                output_worksheet.write_string(start_row,
                                              wake_event_col, "X")
                self.logger.debug("Wakeup event added to row: " +
                                  str(event.time - start_time + 1))
                start_row += 1

            elif isinstance(event, EventSchedSwitch):
                output_worksheet.write_number(start_row,
                                              time_col, event.time - start_time + 1)
                output_worksheet.write_string(start_row,
                                              event_col, str(JobType.SCHED_SWITCH_IN.value))
                output_worksheet.write_number(start_row,
                                              PID_col, event.PID)
                output_worksheet.write_number(start_row,
                                              cpu_col, event.cpu)
                output_worksheet.write_string(start_row,
                                              prev_state_col, event.prev_state)
                output_worksheet.write_number(start_row,
                                              next_pid_col, event.next_pid)

                self.logger.debug("Switch event added to row: " +
                                  str(event.time - start_time + 1))
                start_row += 1

            elif isinstance(event, EventFreqChange):
                output_worksheet.write_number(start_row,
                                              time_col, event.time - start_time + 1)
                output_worksheet.write_string(start_row,
                                              event_col, str(JobType.FREQ_CHANGE.value))
                output_worksheet.write_number(start_row,
                                              freq_freq_col, event.freq)
                output_worksheet.write_number(start_row,
                                              freq_load_col, event.util)
                output_worksheet.write_number(start_row,
                                              cpu_col, event.cpu)
                self.logger.debug("Freq event added to row: " +
                                  str(event.time - start_time + 1))
                start_row += 1

            elif isinstance(event, EventIdle):
                output_worksheet.write_number(start_row,
                                              time_col, event.time - start_time + 1)
                output_worksheet.write_string(start_row,
                                              event_col, str(JobType.IDLE.value))
                output_worksheet.write_number(start_row,
                                              cpu_col, event.cpu)
                output_worksheet.write_number(start_row,
                                              idle_state_col, event.state)
                self.logger.debug("Idle event added to row: " +
                                  str(event.time - start_time + 1))
                start_row += 1
            elif isinstance(event, EventBinderCall):
                output_worksheet.write_number(start_row,
                                              time_col, event.time - start_time + 1)
                output_worksheet.write_string(start_row,
                                              event_col, str(JobType.BINDER_SEND.value))
                output_worksheet.write_number(start_row,
                                              PID_col, event.PID)
                output_worksheet.write_number(start_row,
                                              next_pid_col, event.dest_proc)
                output_worksheet.write_number(start_row,
                                              binder_type_col, event.trans_type.value)
                output_worksheet.write_number(start_row,
                                              binder_ID_col, event.trans_ID)
                output_worksheet.write_number(start_row,
                                              binder_flags_col, event.flags)
                output_worksheet.write_number(start_row,
                                              binder_code_col, event.code)
                start_row += 1
            else:
                self.logger.debug("Unknown event: " + str(event))

        output_workbook.close()

    def process_trace_file(self, filename, PIDt):
        try:
            f = open(filename, "r")
            self.logger.debug("Tracer " + filename + " opened for \
                    processing ")
        except IOError:
            self.logger.error("Could not open trace file" + filename)
            sys.exit("Tracer " + filename + " unable to be opened for processing")

        self.process_trace(f, PIDt, None)

    def process_tracer(self, tracer, PIDt):
        # open trace
        try:
            f = open(tracer.filename, "r")
            self.logger.debug("Tracer " + tracer.filename + " opened for \
                    processing ")
        except IOError:
            self.logger.error("Could not open trace file" + tracer.filename)
            sys.exit("Tracer " + tracer.filename + " unable to be opened for processing")

        self.process_trace(f, PIDt, tracer.metrics)

    def process_trace(self, f, PIDt, metrics=None):

        raw_lines = f.readlines()
        processed_events = []

        if metrics is None:
            metrics = SystemMetrics(adbInterface.current_interface, None, None, None)

        # Filter and sort events
        self.logger.debug("Trace contains " + str(len(raw_lines)) + " lines")

        for line in raw_lines[11:1000]:

            if not self.keep_PID_line(line, PIDt):
                continue

            if "sched_wakeup" in line:
                processed_events.append(self._process_sched_wakeup(line))
                self.logger.debug("Wakeup event line: " + line)

            elif "sched_switch" in line:
                processed_events.append(self._process_sched_switch(line))
                self.logger.debug("Sched switch: " + line)

            elif "cpu_idle" in line:
                processed_events.append(self._process_sched_idle(line))
                self.logger.debug("Idle event line: " + line)

            elif "update_cpu_metric" in line:
                processed_events.append(self._process_sched_freq(line))
                self.logger.debug("Freq event line: " + line)

            elif "binder" in line:
                processed_events.append(self._process_binder_transaction(line))
                self.logger.debug("Binder event line: " + line)

            elif "mali_utilization_stats" in line:
                processed_events.append(self._process_mali_util(line))
                self.logger.debug("Mali util line: " + line)

        if processed_events == []:
            self.logger.debug("Processing trace failed")
            sys.exit("Processing trace failed")

        # export to XLSX
        # self.writeToXlsx(processed_events, op.basename(f.name))

        # generate pointers to most recent nodes for each PID (branch heads)
        process_tree = ProcessTree(PIDt, metrics)

        for x, event in enumerate(processed_events):
            process_tree.handle_event(event)

        draw_graph = Grapher(process_tree)
        draw_graph.drawGraph()
