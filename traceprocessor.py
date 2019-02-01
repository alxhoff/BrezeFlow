import logging
from aenum import Enum
from event import *
import xlsxwriter

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

    def _processSchedWakeup(self, line):
        split_line = line.split()
        #get PID
        pid = int(split_line.split('-')[-1])
        #get time
        time = int(float(split_line[3][:-2]) * 1000000)
        #get cpu
        for x, chunk in enumerate(split_line):
            if "target_cpu=" in chunk:
                cpu = int(chunk[-3:-1])
                break

        return even_wakeup(pid, time, cpu)

    def _processSchedSwitch(self, line):
        events = []
        for x, line in enumerate(tracer_lines, 11):
            split_line = line.split()
            #get  PI

    def _processSchedIdle(self, line):
        split_line = line.split()
        #get time
        time = int(float(split_line[3][:-2]) * 1000000)
        #get cpu
        cpu = int(split_line[6][-1])
        #get idle
        idle = int(split_line[5][6:])

        return event_idle(time, cpu, idle)

    def _processSchedFreq(self, line):
        split_line = line.split()
        #get PID
        pid = int(split_line[0].split('-')[-1])
        #get time
        time = int(float(split_line[3][:-2]) * 1000000)
        #get freq
        freq = int(split_line[9])
        #get load
        load = int(split_line[11])
        #get cpu
        cpu = int(split_line[7])

        return event_freq_change(pid, time, freq, load, cpu)

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
        print raw_lines
        processed_events = []
        #determine tracer type
        self.logger.debug("Trace contains " + str(len(raw_lines)) + " lines")
        for line in raw_lines[11:]:
            if "shed_wakeup" in line:
                processed_events.append(self._processSchedWakeup(line))
                self.logger.debug("Wakeup event line: " + line)
            #elif sched_switch in line:
            #    processed_events = self._processSchedSwitch(raw_lines)
            #    self.logger.debug("Trace " + tracer.filename + " of type switch")
            #    break
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
        freq_freq_col = 2
        freq_load_col = 3
        cpu_col = 4
        wakeup_pid_col = 6
        idle_state_col = 9

        output_worksheet.write_string(0, time_col, "Time")
        output_worksheet.write_string(0, freq_freq_col, "Frequency Change")
        output_worksheet.write_string(0, freq_load_col, "Load")
        output_worksheet.write_string(0, cpu_col, "CPU")
        output_worksheet.write_string(0, wakeup_pid_col, "PID")
        output_worksheet.write_string(0, idle_state_col, "Idle")

        for event in processed_events:
            if isinstance(event, event_wakeup):
                output_worksheet.write_number(event.time - start_time + 1,
                        time_col, event.time - start_time + 1)
                output_worksheet.write_number(event.time - start_time + 1,
                        wakeup_pid_col, event.PID)
                output_worksheet.write_number(event.time - start_time + 1,
                        cpu_col, event.cpu)
                self.logger.debug("Wakeup event added to row: " +
                        str(event.time - start_time + 1))

            #elif isinstance(event, event_run_slice):

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
