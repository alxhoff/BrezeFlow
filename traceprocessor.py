import multiprocessing as multip
import re
import sys
import time

import xlsxwriter

from event import *
from grapher import *


class TraceProcessor:

    def __init__(self, PIDt, filename):
        logging.basicConfig(filename="pytracer.log",
                            format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Trace processor created")
        self.PIDt = PIDt
        self.filename = filename

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
                                              next_pid_col, event.dest_pid)
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

    def process_trace_file(self, filename, metrics, multi, draw):
        try:
            f = open(filename, "r")
            self.logger.debug("Tracer " + filename + " opened for \
                    processing ")
        except IOError:
            self.logger.error("Could not open trace file" + filename)
            sys.exit("Tracer " + filename + " unable to be opened for processing")

        # read temps from file
        SystemMetrics.current_metrics.read_temps()

        self.process_trace(metrics, multi, draw, filename=f)

    def process_tracer(self, tracer, multi, draw):
        # open trace
        try:
            f = open(tracer.filename, "r")
            self.logger.debug("Tracer " + tracer.filename + " opened for \
                    processing ")
        except IOError:
            self.logger.error("Could not open trace file" + tracer.filename)
            sys.exit("Tracer " + tracer.filename + " unable to be opened for processing")

        self.process_trace(tracer.metrics, multi, draw, filename=f)

    def process_tracecmd(self, metrics, multi, draw, TCProcessor):
        SystemMetrics.current_metrics.read_temps()
        self.process_trace(metrics, multi, draw, tracecmd=TCProcessor)


    def process_trace(self, metrics, multi, draw, tracecmd=None, filename=None):
        process_start_time = time.time()
        print "Processing trace"

        start_time = time.time()
        pids = self.PIDt.allPIDStrings[1:]

        if tracecmd is not None:
            processed_events = tracecmd.processed_events
        else:
            if filename is None:
                print "Filename required"
                sys.exit(1)
            raw_lines = filename.readlines()
            processed_events = []

            # Filter and sort events

            line_count = len(raw_lines)
            lines_processed = 0

            if not multi:
                for line in raw_lines[11:]:
                    processed_events.append(process_raw_line(pids, line))

                    print "Processed " + str(lines_processed) + "/" + str(line_count) + "\r",
                    lines_processed += 1
            else:
                print "Running regex parsing on " + str(multip.cpu_count()) + " CPUs"
                poolv = multip.Pool(multip.cpu_count())
                processed_events = [poolv.apply(process_raw_line, args=(pids, line)) for line in raw_lines[11:]]
                poolv.close()
                poolv.join()

        if processed_events == []:
            self.logger.debug("Processing trace failed")
            sys.exit("Processing trace failed")

        print ("Regexing trace took %s seconds" % (time.time() - start_time))

        # export to XLSX
        # self.writeToXlsx(processed_events, op.basename(f.name))

        # generate pointers to most recent nodes for each PID (branch heads)
        process_tree = ProcessTree(self.PIDt, metrics)

        # Create CPU core utilization trees first
        start_time = time.time()
        print "Compiling util trees"
        i = 0
        length = len(processed_events)
        while i < length:
            if isinstance(processed_events[i], EventIdle):
                process_tree.handle_event(processed_events[i])
                del processed_events[i]
                length -= 1
            elif processed_events[i] is None:
                del processed_events[i]
                length -= 1
            else:
                i += 1
        print ("Util trees took %s seconds to build" % (time.time() - start_time))

        # Init GPU util tree
        # set initial time as first event in log as mali util is able to be found via sysfs
        # and as such available from the start and must not be calculated
        # TODO does it matter if the first event is a mali event?
        metrics.sys_util.gpu_utils.init(processed_events[0].time, metrics.gpu_util)

        # compile cluster utilizations
        start_time = time.time()
        print "Compiling cluster util tables"
        for x, cluster in enumerate(metrics.sys_util.cluster_utils):
            cluster.compile_table(metrics.sys_util.core_utils[x * 4: x * 4 + 4])
        print ("Cluster util table generated in %s seconds" % (time.time() - start_time))

        num_events = len(processed_events)
        print "Total events: " + str(num_events)

        start_time = time.time()
        print "Processing events"
        for x, event in enumerate(processed_events):
            print str(x) + "/" + str(num_events) + " " + str(round(float(x)/num_events * 100, 2)) + "%\r",
            process_tree.handle_event(event)
        print ("All events handled in %s seconds" % (time.time() - start_time))

        start_time = time.time()
        print "Finishing process tree"
        process_tree.finish_tree( 0, self.filename)
        print ("Finished tree in %s seconds" % (time.time() - start_time))

        if draw:
            start_time = time.time()
            draw_graph = Grapher(process_tree)
            draw_graph.drawGraph()
            print ("Graph drawn in %s seconds" % (time.time() - start_time))

        print ("Processing finished in %s seconds" % (time.time() - process_start_time))


def keep_PID_line(pids, line):
    if any(re.search("-(" + str(pid) + ") +|=(" + str(pid) + ") ", line) for pid in pids):
        return True
    return False


def process_raw_line(pids, line):
    regex_line = re.findall(": ([a-z_]+): ", line)

    # if regex_line[0] == "sched_wakeup" in line:
    #     # TODO customized regex
    #     if not keep_PID_line(pids, line):
    #         return None
    #     return process_sched_wakeup(line)

    try:
        if regex_line[0] == "sched_switch" in line:
            # if not keep_PID_line(pids, line):
            #     return None
            return process_sched_switch(line, pids)

        elif regex_line[0] == "cpu_idle" in line:
            return process_sched_idle(line)

        elif regex_line[0] == "update_cpu_metric" in line:
            return process_cpu_metric(line)

        elif regex_line[0] == "binder_transaction" in line:
            # if not keep_PID_line(pids, line):
            #     return None
            return process_binder_transaction(line, pids)

        elif regex_line[0] == "mali_utilization_stats" in line:
            return process_mali_util(line)
    except IndexError:
        # Irrelevant log messages
        return None

    return None


def process_sched_wakeup(line):
    pid = int(re.findall("-(\d+) *\[", line)[0])
    time = int(round(float(re.findall(" (\d+\.\d+):", line)[0]) * 1000000))
    cpu = int(re.findall(" target_cpu=(\d+)", line)[0])
    name = re.findall("^ *(.+?)-\d+ +", line)[0]

    return EventWakeup(pid, time, cpu, name)


def process_sched_switch(line, pids):
    regex_line = re.findall(
        "^ *(.+?)-(\d+) +\[(\d{3})\] .{4} +(\d+.\d+).+prev_state=([RSDx]{1})[+]? ==> next_comm=.+ next_pid=(\d+)",
        line)

    name = regex_line[0][0]
    prev_state = regex_line[0][4]
    next_pid = int(regex_line[0][5])
    pid = int(regex_line[0][1])
    cpu = int(regex_line[0][2])
    time = int(float(regex_line[0][3]) * 1000000)

    if pid in pids or next_pid in pids:
        return EventSchedSwitch(pid, time, cpu, name, prev_state, next_pid)
    else:
        return None


def process_sched_idle(line):
    regex_line = re.findall("\[(\d{3})\] .{4} +(\d+.\d+): cpu_idle: state=(\d+)", line)

    time = int(float(regex_line[0][1]) * 1000000)
    cpu = int(regex_line[0][0])
    state = int(regex_line[0][2])

    return EventIdle(time, cpu, "idle", state)


def process_cpu_metric(line):
    regex_line = re.findall(
        "-(\d+) +\[(\d{3})\] .{4} +(\d+.\d+): update_cpu_metric: cpu_load: cpu: (\d+) freq: (\d+) load: (\d+)",
        line)

    pid = int(regex_line[0][0])
    cpu = int(regex_line[0][1])
    time = int(float(regex_line[0][2]) * 1000000)
    target_cpu = int(regex_line[0][3])
    freq = int(regex_line[0][4]) * 1000
    util = int(regex_line[0][5])

    return EventFreqChange(pid, time, cpu, freq, util, target_cpu)


def process_binder_transaction(line, pids):
    regex_line = re.findall(
        "^ *(.*)-(\d+) +\[(\d{3})\] .{4} +(\d+.\d+): binder_transaction: transaction=\d+ dest_node=\d+ dest_proc=(\d+) dest_thread=(\d+) reply=(\d) flags=(0x[0-9a-f]+) code=(0x[0-9a-f]+)",
        line)

    name = regex_line[0][0]
    pid = int(regex_line[0][1])
    cpu = int(regex_line[0][2])
    time = int(float(regex_line[0][3]) * 1000000)
    to_proc = int(regex_line[0][5])
    if to_proc == 0:
        to_proc = int(regex_line[0][4])
    reply = int(regex_line[0][6])
    flags = int(regex_line[0][7], 16)
    code = int(regex_line[0][8], 16)

    if pid in pids or to_proc in pids:
        return EventBinderCall(pid, time, cpu, name, reply, to_proc, flags, code)
    else:
        return None


def process_mali_util(line):
    regex_line = re.findall(
        "-(\d+) +\[(\d{3})\] .{4} +(\d+.\d+): mali_utilization_stats: util=(\d+) norm_util=\d+ norm_freq=(\d+)",
        line)

    pid = int(regex_line[0][0])
    cpu = int(regex_line[0][1])
    time = int(float(regex_line[0][2]) * 1000000)
    util = int(regex_line[0][3])
    freq = int(regex_line[0][4]) * 1000000

    return EventMaliUtil(pid, time, cpu, util, freq)
