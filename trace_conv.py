#!/usr/bin/python2

import sys
import csv
import json
import argparse
from tracecmd import *

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input-file", nargs=1, default=["trace.dat"],
                    help="Input trace file")
parser.add_argument("-o", "--output-folder", nargs=1, default=["."],
                    help="Folder data will be written to")
args = parser.parse_args()

# labels for the powerlogger CSV file
PL_TIME = 'Time [s]'
PL_TIME_EXT = 'Time External [ns]'
PL_POWER_A15 = 'Power A15 [W]'
PL_POWER_A7 = 'Power A7 [W]'
PL_POWER_MEM = 'Power Mem [W]'
PL_POWER_GPU = 'Power GPU [W]'
PL_POWER_TOTAL = 'Total Power [W]'
PL_MALI_UTIL = 'Mali Util [%]'
PL_MALI_FREQ = 'Mali Freq [Hz]'
PL_MALI_TEMP = 'Mali Temp [C]'
PL_TEMP_A15_1 = 'Temp A15 C1 [C]'
PL_TEMP_A15_2 = 'Temp A15 C2 [C]'
PL_TEMP_A15_3 = 'Temp A15 C3 [C]'
PL_TEMP_A15_4 = 'Temp A15 C4 [C]'
PL_FREQ_A15 = 'Freq A15 [Hz]'
PL_FREQ_A7 = 'Freq A7 [Hz]'
PL_USAGE_A15_1 = 'Usage A15 C1 [%]'
PL_USAGE_A15_2 = 'Usage A15 C2 [%]'
PL_USAGE_A15_3 = 'Usage A15 C3 [%]'
PL_USAGE_A15_4 = 'Usage A15 C4 [%]'
PL_USAGE_A15_AVG = 'Usage A15 Avg [%]'
PL_USAGE_A7_1 = 'Usage A7 C1 [%]'
PL_USAGE_A7_2 = 'Usage A7 C2 [%]'
PL_USAGE_A7_3 = 'Usage A7 C3 [%]'
PL_USAGE_A7_4 = 'Usage A7 C4 [%]'
PL_USAGE_A7_AVG = 'Usage A7 Avg [%]'

PL_ETH0_RX = 'Usage ETH0 RX [#]'
PL_ETH0_TX = 'Usage ETH0 TX [#]'


class CPUInfo:
    def __init__(self, nr):
        self.nr = nr
        self.online = -1
        self.load = -1
        self.freq = -1


class MeasurementInfo:
    def __init__(self, uptime_ts, raw_ts, real_ts):
        self.utime_ts = uptime_ts
        self.raw_ts = raw_ts
        self.real_ts = real_ts
        self.a15_power = -1
        self.a7_power = -1
        self.mem_power = -1
        self.gpu_power = -1
        self.gpu_load = -1
        self.gpu_freq = -1
        self.gpu_temp = -1
        self.a15_0_temp = -1
        self.a15_1_temp = -1
        self.a15_2_temp = -1
        self.a15_3_temp = -1
        self.rx_packets = -1
        self.rx_bytes = -1
        self.tx_packets = -1
        self.tx_bytes = -1
        self.cpus = {}
        self.threads = {}

    def get_cpu(self, cpu):
        if (not cpu in self.cpus):
            self.cpus[cpu] = CPUInfo(cpu)
        return self.cpus[cpu]


class ChromeEvent(object):
    def __init__(self, ts):
        self.ts = ts


class TouchStartEvent(ChromeEvent):
    def __init__(self, ts, was_active):
        super(TouchStartEvent, self).__init__(ts)
        self.was_active = was_active


class TouchStartNotifierEvent(ChromeEvent):
    def __init__(self, ts, dummy):
        super(TouchStartNotifierEvent, self).__init__(ts)
        self.dummy = dummy


class ScrollSpeedEvent(ChromeEvent):
    def __init__(self, ts, scroll_speed_x, scroll_speed_y):
        super(ScrollSpeedEvent, self).__init__(ts)
        self.scroll_speed_x = scroll_speed_x
        self.scroll_speed_y = scroll_speed_y


class PhaseChangeEvent(ChromeEvent):
    def __init__(self, ts, use_case, rail_mode, phase):
        super(PhaseChangeEvent, self).__init__(ts)
        self.use_case = use_case
        self.rail_mode = rail_mode
        self.phase = phase


class A15OnStopEvent(ChromeEvent):
    def __init__(self, ts, cpu):
        super(A15OnStopEvent, self).__init__(ts)
        self.cpu = cpu


class A15OnStartEvent(ChromeEvent):
    def __init__(self, ts, cpu):
        super(A15OnStartEvent, self).__init__(ts)
        self.cpu = cpu


class A15OffStopEvent(ChromeEvent):
    def __init__(self, ts, cpu):
        super(A15OffStopEvent, self).__init__(ts)
        self.cpu = cpu


class A15OffStartEvent(ChromeEvent):
    def __init__(self, ts, cpu):
        super(A15OffStartEvent, self).__init__(ts)
        self.cpu = cpu


class RunInfo:
    def __init__(self):
        self.chrome_events = []
        self.measurements = []

    def new_chrome_event(self, ev):
        if (ev.name == "touch_start"):
            a = ev.num_field("was_active")
            self.chrome_events.append(TouchStartEvent(ev.ts, a))
        elif (ev.name == "touch_start_notifier"):
            d = ev.num_field("dummy")
            self.chrome_events.append(TouchStartEvent(ev.ts, d))
        elif (ev.name == "scroll_speed"):
            x = ev.num_field("scroll_speed_x")
            # this is ugly, but we always get unsigned values
            if x > 0x7FFFFFFF:
                x -= 0x100000000
            y = ev.num_field("scroll_speed_y")
            if y > 0x7FFFFFFF:
                y -= 0x100000000
            self.chrome_events.append(ScrollSpeedEvent(ev.ts, x, y))
        elif (ev.name == "phase_change"):
            u = ev.num_field("use_case")
            r = ev.num_field("rail_mode")
            p = ev.num_field("phase")
            self.chrome_events.append(PhaseChangeEvent(ev.ts, u, r, p))
        elif (ev.name == "a15_on_stop"):
            cpu = ev.num_field("cpu")
            self.chrome_events.append(A15OnStopEvent(ev.ts, cpu))
        elif (ev.name == "a15_on_start"):
            cpu = ev.num_field("cpu")
            self.chrome_events.append(A15OnStartEvent(ev.ts, cpu))
        elif (ev.name == "a15_off_stop"):
            cpu = ev.num_field("cpu")
            self.chrome_events.append(A15OffStopEvent(ev.ts, cpu))
        elif (ev.name == "a15_off_start"):
            cpu = ev.num_field("cpu")
            self.chrome_events.append(A15OffStartEvent(ev.ts, cpu))
        else:
            raise Exception("Unknown chrome event: %s" % (ev.name))

    def new_iteration(self, ev):
        uptime_ts = ev.ts
        raw_ts = ev.num_field("raw")
        if (not raw_ts):
            raw_ts = 0
        real_ts = ev.num_field("real")
        if (not real_ts):
            real_ts = 0
        self.measurements.append(MeasurementInfo(uptime_ts, raw_ts, real_ts))

    def new_measurement(self, ev):
        if (ev.name == "mali"):
            load = ev.num_field("load")
            freq = ev.num_field("freq")
            self.measurements[-1].gpu_load = load
            self.measurements[-1].gpu_freq = freq
        elif (ev.name == "cpu_info"):
            cpu = ev.num_field("cpu")
            load = 0
            online = ev.num_field("online")
            system = ev.num_field("system")
            user = ev.num_field("user")
            idle = ev.num_field("idle")

            # the time granularity might be too small. E.g. for 2ms we
            # will either get 0 or 100 % load. Go back in history to
            # compute values more reasonable
            i = -2
            while i >= -len(self.measurements):
                diff_ns = self.measurements[-1].raw_ts - self.measurements[i].raw_ts
                # 20 ms back in time if possible (otherwise take first sample)
                if i != -len(self.measurements):
                    if diff_ns < 20000000:
                        i = i - 1
                        continue

                prev = self.measurements[i].get_cpu(cpu)
                diff_user = user - prev.user
                diff_system = system - prev.system
                diff_idle = idle - prev.idle

                diff_total = diff_user + diff_system + diff_idle
                if (diff_total != 0):
                    load = ((diff_system + diff_user) * 100) / diff_total
                break

            if (load > 100):
                load = 100

            self.measurements[-1].get_cpu(cpu).online = online
            self.measurements[-1].get_cpu(cpu).load = load
            self.measurements[-1].get_cpu(cpu).system = system
            self.measurements[-1].get_cpu(cpu).user = user
            self.measurements[-1].get_cpu(cpu).idle = idle
        elif (ev.name == "cpu_freq"):
            cpu = ev.num_field("cpu")
            freq = ev.num_field("freq")
            # 0 and 4 are traced, let's expand it to the others
            for i in range(cpu, cpu + 4):
                self.measurements[-1].get_cpu(cpu).freq = freq
        elif (ev.name == "ina231"):
            a15 = ev.num_field("a15")
            a7 = ev.num_field("a7")
            mem = ev.num_field("mem")
            gpu = ev.num_field("gpu")
            self.measurements[-1].a15_power = a15
            self.measurements[-1].a7_power = a7
            self.measurements[-1].mem_power = mem
            self.measurements[-1].gpu_power = gpu
        elif (ev.name == "exynos_temp"):
            a15_0_temp = ev.num_field("t0")
            a15_1_temp = ev.num_field("t1")
            a15_2_temp = ev.num_field("t2")
            a15_3_temp = ev.num_field("t3")
            gpu_temp = ev.num_field("t4")
            self.measurements[-1].a15_0_temp = a15_0_temp
            self.measurements[-1].a15_1_temp = a15_1_temp
            self.measurements[-1].a15_2_temp = a15_2_temp
            self.measurements[-1].a15_3_temp = a15_3_temp
            self.measurements[-1].gpu_temp = gpu_temp
        elif (ev.name == "net_stats"):
            rx_packets = ev.num_field("rx_packets")
            rx_bytes = ev.num_field("rx_bytes")
            tx_packets = ev.num_field("tx_packets")
            tx_bytes = ev.num_field("tx_bytes")
            self.measurements[-1].rx_packets = rx_packets
            self.measurements[-1].rx_bytes = rx_bytes
            self.measurements[-1].tx_packets = tx_packets
            self.measurements[-1].tx_bytes = tx_bytes
        else:
            raise Exception("Unknown measurement event: %s" % (ev.name))


class ThreadInfo:
    def __init__(self, pid, ppid, comm):
        self.pid = pid
        self.ppid = ppid
        self.comm = comm
        self.last_cpu = 0


class ThreadRunInfo:
    def __init__(self, thread, start, stop):
        self.thread = thread
        self.start = start
        self.stop = stop


class TraceStoreState:
    INIT = 1
    START = 2
    ITERATION = 3


class TraceStore:
    def __init__(self, trace):
        self.t = trace
        self.state = TraceStoreState.INIT
        self.runs = []
        self.threads = {}
        self.cpu_activity = {}

        ev = self.t.read_next_event()
        self._process_event(ev)
        while ev:
            ev = self.t.read_next_event()
            self._process_event(ev)

    def _is_sys_logger_event(self, ev):
        # checking for ev.comm does not work reliably
        if (ev.name == "enabled" or
            ev.name == "iteration" or
            ev.name == "mali" or
            ev.name == "cpu_info" or
            ev.name == "cpu_freq" or
            ev.name == "ina231" or
            ev.name == "exynos_temp" or
                ev.name == "net_stats"):
            return True
        return False

    def _is_iteration_marker(self, ev):
        if (ev.name == "iteration"):
            return True
        return False

    def _is_start_marker(self, ev):
        if (ev.name == "enabled"):
            state = ev.num_field("enabled")
            if (state == 1):
                return True
        return False

    def _is_end_marker(self, ev):
        if (ev.name == "enabled"):
            state = ev.num_field("enabled")
            if (state == 0):
                return True
        return False

    def _is_chrome_event(self, ev):
        if (ev.name == "scroll_speed" or
            ev.name == "phase_change" or
            ev.name == "a15_on_stop" or
            ev.name == "a15_on_start" or
            ev.name == "a15_off_stop" or
            ev.name == "a15_off_start" or
            ev.name == "touch_start_notifier" or
                ev.name == "touch_start"):
            return True
        return False

    def _is_sched_event(self, ev):
        if (ev.name == "sched_wakeup" or
            ev.name == "sched_wakeup_new" or
            ev.name == "sched_stat_runtime" or
                ev.name == "sched_process_fork"):
            return True
        return False

    def _process_sched_event(self, ev):
        '''
        fork events are the only way to detect child->parent
        relationships. We therefore have to start tracing before
        starting Chrome.
        '''
        if ev.name == "sched_process_fork":
            pid = ev.num_field("child_pid")
            ppid = ev.num_field("parent_pid")
            pcomm = ev.num_field("parent_comm")
            comm = ev.str_field("child_comm")
            if not ppid in self.threads:
                self.threads[ppid] = ThreadInfo(ppid, -1, pcomm)
            self.threads[pid] = ThreadInfo(pid, ppid, comm)
            return

        pid = ev.num_field("pid")
        comm = ev.str_field("comm")
        if not pid in self.threads:
            self.threads[pid] = ThreadInfo(pid, -1, "")
        t = self.threads[pid]

        '''
        The comm might change during runtime. Most importantly
        it will be the same as the parent comm on a "real" fork
        (not a clone). So use the last known value instead.
        '''
        if t.comm != comm:
            t.comm = comm

        '''
        Even if a process is migrated, first the runtime is accounted
        and then it is woken up again. So there is no need to trace
        thread migration.
        '''
        if ev.name == "sched_wakeup" or ev.name == "sched_wakeup_new":
            # indicates the thread for the next runtime event
            t.last_cpu = ev.num_field("target_cpu")
        elif ev.name == "sched_stat_runtime":
            # runtime since last woken up
            if not t.last_cpu in self.cpu_activity:
                self.cpu_activity[t.last_cpu] = []
            runtime = ev.num_field("runtime")
            stop = ev.ts
            start = ev.ts - runtime

            '''
            strange but true, as the tracepoint is written
            slightly after the time has been measured, and
            tracepoints time jitters, we can get slight
            overlaps if CPUs are running at full load. (e.g. when
            the timer kicks in and just accounts for the current
            task).
            '''
            if len(self.cpu_activity[t.last_cpu]) > 1:
                lastRun = self.cpu_activity[t.last_cpu][-1]
                if lastRun.stop >= start:
                    start = lastRun.stop + 1

            if start >= stop:
                print("Dropping overlapping runtime")
                return

            info = ThreadRunInfo(t, start, stop)
            self.cpu_activity[t.last_cpu].append(info)
        else:
            raise Exception("Unknown sched event: %s" % (ev.name))

    def _process_event(self, ev):
        if (not ev):
            return

        '''
        We get all events from trace-cmd sorted by ts, even when
        recorded on different CPUs. Therefore no manual sorting necessary.
        '''

        '''
        We handle all scheduler events before all runs, because
        run information might be overlapping and fork events are
        required even before measurements started (to detect
        parent -> child relations).
        '''
        if self._is_sched_event(ev):
            self._process_sched_event(ev)
            return

        '''
        As we might have some unrelated events in here, we'll simply drop them.
        '''
        if (not (self._is_sys_logger_event(ev) or self._is_chrome_event(ev))):
            return
        if (self.state == TraceStoreState.INIT):
            if (self._is_start_marker(ev)):
                self.state = TraceStoreState.START
                self.runs.append(RunInfo())
            # drop all traces (also chrome events) before the start event
            return

        # handle chrome events
        if (self._is_chrome_event(ev)):
            self.runs[-1].new_chrome_event(ev)
            return

        # handle sys_logger measurements
        if (self.state == TraceStoreState.START):
            if (self._is_iteration_marker(ev)):
                self.runs[-1].new_iteration(ev)
                self.state = TraceStoreState.ITERATION
            elif (self._is_end_marker(ev)):
                self.state = TraceStoreState.INIT
                print "WARNING: Empty run."
            elif (self._is_start_marker(ev)):
                print "WARNING: Unexpected start marker, dropping ..."
            else:
                print "WARNING: Event before iteration marker, dropping ..."
        elif (self.state == TraceStoreState.ITERATION):
            if (self._is_iteration_marker(ev)):
                self.runs[-1].new_iteration(ev)
            elif (self._is_end_marker(ev)):
                self.state = TraceStoreState.INIT
            elif (self._is_start_marker(ev)):
                print "WARNING: Unexpected start marker, dropping ..."
            else:
                self.runs[-1].new_measurement(ev)

    def write_powerlogger_csv(self, output_folder, index):
        run = self.runs[index]
        filename = output_folder + "/powerlogger-%d.csv" % index

        with open(filename, 'w') as csvfile:
            fieldnames = [
                PL_TIME,
                PL_TIME_EXT,
                PL_POWER_A15,
                PL_POWER_A7,
                PL_POWER_MEM,
                PL_POWER_GPU,
                PL_POWER_TOTAL,
                PL_MALI_UTIL,
                PL_MALI_FREQ,
                PL_MALI_TEMP,
                PL_TEMP_A15_1,
                PL_TEMP_A15_2,
                PL_TEMP_A15_3,
                PL_TEMP_A15_4,
                PL_FREQ_A15,
                PL_FREQ_A7,
                PL_USAGE_A15_1,
                PL_USAGE_A15_2,
                PL_USAGE_A15_3,
                PL_USAGE_A15_4,
                PL_USAGE_A15_AVG,
                PL_USAGE_A7_1,
                PL_USAGE_A7_2,
                PL_USAGE_A7_3,
                PL_USAGE_A7_4,
                PL_USAGE_A7_AVG,
                PL_ETH0_RX,
                PL_ETH0_TX,
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for m in run.measurements:
                writer.writerow({
                    PL_TIME: m.raw_ts/1000000000.0,
                    PL_TIME_EXT: m.real_ts,
                    PL_POWER_A15: m.a15_power / 1000000.0
                    if m.a15_power != -1 else 0,
                    PL_POWER_A7: m.a7_power / 1000000.0
                    if m.a7_power != -1 else 0,
                    PL_POWER_MEM: m.mem_power / 1000000.0
                    if m.mem_power != -1 else 0,
                    PL_POWER_GPU: m.gpu_power / 1000000.0
                    if m.gpu_power != -1 else 0,
                    PL_POWER_TOTAL: (m.a15_power + m.a7_power
                                     + m.mem_power + m.gpu_power) / 1000000.0,
                    PL_TEMP_A15_1: m.a15_0_temp / 1000
                    if m.a15_0_temp != -1 else -1,
                    PL_TEMP_A15_2: m.a15_1_temp / 1000
                    if m.a15_1_temp != -1 else -1,
                    PL_TEMP_A15_3: m.a15_2_temp / 1000
                    if m.a15_2_temp != -1 else -1,
                    PL_TEMP_A15_4: m.a15_3_temp / 1000
                    if m.a15_3_temp != -1 else -1,
                    PL_MALI_UTIL: m.gpu_load,
                    PL_MALI_FREQ: m.gpu_freq,
                    PL_MALI_TEMP: m.gpu_temp / 1000
                    if m.gpu_temp != -1 else -1,
                    PL_FREQ_A15: m.get_cpu(4).freq,
                    PL_FREQ_A7: m.get_cpu(0).freq,
                    PL_USAGE_A15_1: m.get_cpu(4).load,
                    PL_USAGE_A15_2: m.get_cpu(5).load,
                    PL_USAGE_A15_3: m.get_cpu(6).load,
                    PL_USAGE_A15_4: m.get_cpu(7).load,
                    PL_USAGE_A15_AVG: (m.get_cpu(4).load + m.get_cpu(5).load + m.get_cpu(6).load + m.get_cpu(7).load)/4,
                    PL_USAGE_A7_1: m.get_cpu(0).load,
                    PL_USAGE_A7_2: m.get_cpu(1).load,
                    PL_USAGE_A7_3: m.get_cpu(2).load,
                    PL_USAGE_A7_4: m.get_cpu(3).load,
                    PL_USAGE_A7_AVG: (m.get_cpu(0).load + m.get_cpu(1).load + m.get_cpu(2).load + m.get_cpu(3).load)/4,
                    PL_ETH0_RX: m.rx_packets,
                    PL_ETH0_TX: m.tx_packets,
                })

    def write_powerlogger_csvs(self, output_folder):
        for index in range(len(self.runs)):
            self.write_powerlogger_csv(output_folder, index)

    def write_threads_csv(self, output_folder):
        filename = output_folder + "/threads.csv"

        with open(filename, 'w') as csvfile:
            fieldnames = [
                "pid",
                "comm",
                "ppid",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for key in self.threads:
                t = self.threads[key]
                writer.writerow({
                    "pid": t.pid,
                    "comm": t.comm,
                    "ppid": t.ppid,
                })

    def write_cpu_activity_csv(self, cpu, output_folder, index):
        run = self.runs[index]
        filename = output_folder + "/cpu_activity_%d-%d.csv" % (cpu, index)

        with open(filename, 'w') as csvfile:
            fieldnames = [
                "start",
                "stop",
                "pid",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # empty file if we don't have start and stop
            if len(run.measurements) < 2:
                return
            start = run.measurements[0].raw_ts
            stop = run.measurements[-1].raw_ts

            '''
            We will be extracting just that part that belongs
            to a measurement run. The other stuff we can drop
            (only used to monitor forks)
            '''
            for r in self.cpu_activity[cpu]:
                if r.start > stop:
                    break
                if r.stop < start:
                    continue

                # cut overlapping runs to fit our range
                writer.writerow({
                    "start": max(r.start, start),
                    "stop": min(r.stop, stop),
                    "pid": r.thread.pid,
                })

    def write_cpu_activity_csvs(self, output_folder):
        for cpu in self.cpu_activity:
            for index in range(len(self.runs)):
                self.write_cpu_activity_csv(cpu, output_folder, index)

    def write_task_load_log(self, output_folder, index):
        run = self.runs[index]
        filename = output_folder + "/task_load-%d.log" % index

        # this whole structure is questionable, but it is the actual format
        data = {}
        ts = []
        phases = []
        task_data = []
        data["traceEvents"] = []
        data["traceEvents"].append({"ts": ts})
        data["traceEvents"].append({"phases": phases})
        # we are not including task load data, just phases

        for m in self.runs[index].measurements:
            ts.append(m.raw_ts)

        for e in self.runs[index].chrome_events:
            if (isinstance(e, PhaseChangeEvent)):
                phases.append({"ts": e.ts,
                               "use_case": e.use_case,
                               "rail_mode": e.rail_mode,
                               "phase": e.phase})

        with open(filename, 'w') as outfile:
            json.dump(data, outfile)

    def write_task_load_logs(self, output_folder):
        for index in range(len(self.runs)):
            self.write_task_load_log(output_folder, index)

    def write_cg_event_csv(self, output_folder, index):
        run = self.runs[index]
        filename = output_folder + "/cg_events-%d.csv" % index

        with open(filename, 'w') as outfile:
            prev_phase = -1
            for e in self.runs[index].chrome_events:
                type = 0
                data = 0
                ts = e.ts
                if (isinstance(e, ScrollSpeedEvent)):
                    type = 13
                    data = e.scroll_speed_y
                elif (isinstance(e, TouchStartEvent)):
                    type = 14
                    data = e.was_active
                elif (isinstance(e, TouchStartNotifierEvent)):
                    type = 6
                    data = e.dummy
                elif (isinstance(e, PhaseChangeEvent)):
                    type = 11
                    data = e.phase
                    if prev_phase == e.phase:
                        continue
                    prev_phase = data
                elif (isinstance(e, A15OnStartEvent)):
                    type = 1
                    data = e.cpu
                elif (isinstance(e, A15OnStopEvent)):
                    type = 2
                    data = e.cpu
                elif (isinstance(e, A15OffStartEvent)):
                    type = 3
                    data = e.cpu
                elif (isinstance(e, A15OffStopEvent)):
                    type = 4
                    data = e.cpu
                outfile.write("%u, %u, %d\n" % (ts, type, data))

    def write_cg_event_csvs(self, output_folder):
        for index in range(len(self.runs)):
            self.write_cg_event_csv(output_folder, index)


if __name__ == "__main__":
    try:
        trace = Trace(args.input_file[0])
    except Exception, e:
        print "File could not be read: %s" % str(e)
        sys.exit(1)

    store = TraceStore(trace)
    store.write_powerlogger_csvs(args.output_folder[0])
    store.write_task_load_logs(args.output_folder[0])
    store.write_cg_event_csvs(args.output_folder[0])
    store.write_threads_csv(args.output_folder[0])
    store.write_cpu_activity_csvs(args.output_folder[0])
