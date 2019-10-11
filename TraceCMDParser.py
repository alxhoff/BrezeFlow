#!/usr/bin/env python

"""
Uses the tracecmd python module to parse the tracecmd events, found in a tracecmd .dat file, into event
objects, found in the SystemEvents module of the energy debugger.
"""

import sys

from SystemEvents import *
from tracecmd import Trace

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"


class EventCounts:
    """ Used simply to track the number of different events that occured throughout the duration of a trace.
    """

    def __init__(self):
        self.sched_switch = 0
        self.cpu_idle = 0
        self.update_cpu_metric = 0
        self.cpu_freq = 0
        self.binder_transaction = 0
        self.mali = 0
        self.temp = 0


class TracecmdProcessor:
    """ Using the tracecmd backend the ftrace events, recorded using tracecmd, are processed sequentially once
    the trace date has been loaded.

    """

    def __init__(self, filename, preamble):
        self.processed_events = []
        self.temp_events = []
        self.idle_events = []
        try:
            self.trace = Trace(str(filename))
        except Exception, e:
            print "Tracecmd file could not be read: %s" % str(e)
            sys.exit(1)

        self.event_count = EventCounts()
        self._process_trace(preamble)

    def print_event_count(self):
        try:
            print "--- Total events: " + str(self.event_count.sched_switch + self.event_count.cpu_idle
                                             + self.event_count.sched_switch + self.event_count.binder_transaction +
                                             + self.event_count.cpu_freq + self.event_count.mali)
            print "------ Sched switch: " + str(self.event_count.sched_switch)
            print "------ CPU idle: " + str(self.event_count.cpu_idle)
            print "------ CPU freq: " + str(self.event_count.cpu_freq)
            print "------ Binder transactions: " + str(self.event_count.binder_transaction)
            print "------ Mali: " + str(self.event_count.mali)
            print "------ Temp: " + str(self.event_count.temp)
        except Exception, e:
            print("Print event count failed, %s" % e)

    def _process_trace(self, preamble):
        """ Sequentially process trace events.

        :return:
        """
        start_time = 0
        event = self.trace.read_next_event()
        # Discard the first 2 seconds of tracing as syslogger initially causes
        # spikes in system power
        if start_time == 0 and event:
            start_time = int(round(event.ts / 1000.0)) + (preamble * 1000000)
        while event:
            if int(round(event.ts / 1000.0)) > start_time:
                self._handle_event(event)
            event = self.trace.read_next_event()

    def _handle_event(self, event):
        """ Create an appropriate Event class child object that is then added to the list of unprocessed
        python objects.

        :param event: Tracecmd event object to be processed into Event object
        """

        if not event:
            return

        if event.name == "sched_switch":

            self.event_count.sched_switch += 1

            prev_state = 'R'
            prev_state_int = event.num_field("prev_state")
            if prev_state_int == 1:
                prev_state = 'S'
            elif prev_state_int == 2:
                prev_state = 'D'
            elif prev_state_int == 4:
                prev_state = 'T'
            elif prev_state_int == 8:
                prev_state = 't'
            elif prev_state_int == 16:
                prev_state = 'Z'
            elif prev_state_int == 32:
                prev_state = 'X'
            elif prev_state_int == 64:
                prev_state = 'x'
            elif prev_state_int == 128:
                prev_state = 'K'
            elif prev_state_int == 256:
                prev_state = 'W'
            elif prev_state_int == 512:
                prev_state = 'P'

            name = event.str_field("prev_comm")
            next_pid = event.num_field("next_pid")
            next_name = event.str_field("next_comm")
            self.processed_events.append(EventSchedSwitch(pid=event.pid, ts=int(round(event.ts / 1000.0)),
                                                          cpu=event.cpu, name=name, prev_state=prev_state,
                                                          next_pid=next_pid, next_name=next_name))
        elif event.name == "cpu_idle":
            self.event_count.cpu_idle += 1

            state = event.num_field("state")
            state = 1 if state == 4294967295 else 0
            self.idle_events.append(EventIdle(ts=int(round(event.ts / 1000.0)), cpu=event.cpu,
                                              name=event.name, state=state))

        elif event.name == "cpu_freq":
            self.event_count.cpu_freq += 1

            target_cpu = event.num_field("cpu")
            freq = event.num_field("freq") * 1000
            self.processed_events.append(EventFreqChange(pid=event.pid, ts=int(round(event.ts / 1000.0)),
                                                         cpu=event.cpu, freq=freq, util=0, target_cpu=target_cpu))

        elif event.name == "binder_transaction":
            self.event_count.binder_transaction += 1

            reply = event.num_field("reply")
            flags = event.num_field("flags")
            code = event.num_field("code")
            to_proc = event.num_field("to_proc")
            to_thread = event.num_field("to_thread")
            if to_thread == 0:
                to_thread = to_proc
            trans_num = event.num_field("debug_id")

            self.processed_events.append(EventBinderTransaction(pid=event.pid, ts=int(round(event.ts / 1000.0)),
                                                                cpu=event.cpu, name=event.name, reply=reply,
                                                                dest_proc=to_proc, target_pid=to_thread, flags=flags,
                                                                code=code, tran_num=trans_num))

        elif event.name == "mali":
            self.event_count.mali += 1

            util = event.num_field("load")
            freq = event.num_field("freq") * 1000000

            self.processed_events.append(EventMaliUtil(pid=event.pid, ts=int(round(event.ts / 1000.0)), cpu=event.cpu,
                                                       util=util, freq=freq))

        elif event.name == "exynos_temp":
            self.event_count.temp += 1

            big0 = event.num_field("t0") / 1000
            big1 = event.num_field("t1") / 1000
            big2 = event.num_field("t2") / 1000
            big3 = event.num_field("t3") / 1000
            little = (big0 + big1 + big2 + big3) / 4.0
            gpu = event.num_field("t4") / 1000

            self.temp_events.append(EventTempInfo(ts=int(round(event.ts / 1000.0)), cpu=event.cpu,
                                                                  big0=big0, big1=big1, big2=big2, big3=big3,
                                                                  little=little, gpu=gpu))

        else:
            pass  # print "Unknown event %s" % event.name
