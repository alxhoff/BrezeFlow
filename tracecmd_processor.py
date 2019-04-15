import sys
import csv
import json
import argparse
from tracecmd import *
from traceprocessor import *

class TracecmdProcessor:

    def __init__(self, filename):
        self.processed_events = []
        try:
            self.trace = Trace(filename)
        except Exception, e:
            print "Tracecmd file could not be read: %s" % str(e)
            sys.exit(1)

        self.processed_trace = self.process_trace()

    def process_trace(self):
        event = self.trace.read_next_event()
        self.handle_event(event)
        while event:
            event = self.trace.read_next_event()
            self.handle_event(event)

    def handle_event(self, event):

        if not event:
            return

        if event.name == "sched_switch":
            prev_state = 'S'
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

            next_pid = event.num_field("next_pid")
            self.processed_events.append(EventSchedSwitch(event.pid, event.ts,
                                event.cpu, event.name, prev_state, next_pid))
            return
        elif event.name == "cpu_idle":
            state = event.num_field("state")
            self.processed_events.append(EventIdle(event.ts, event.cpu, event.name,
                                state))
            return
        elif event.name == "update_cpu_metric":
            print "wait here"
            return
        elif event.name == "cpu_freq":
            CPU = event.num_field("cpu")
            freq = event.num_field("freq")

                    self.processed_events.append(EventFreqChange(event.pid, event.ts,
                                event.cpu, freq, 0, i))

                    self.processed_events.append(EventFreqChange(event.pid, event.ts,
                                 event.cpu, freq, 0, i + 4))
            return
        elif event.name == "binder_transaction":
            reply = event.num_field("reply")
            flags = event.num_field("flags")
            code = event.num_field("code")
            to_proc = event.num_field("to_thread")
            if to_proc == 0:
                to_proc = event.num_field("to_proc")

            self.processed_events.append(EventBinderCall(event.pid, event.ts,
                                event.cpu, event.name, reply, to_proc, flags, code))
            return
        elif event.name == "mali_utilization_stats":
            util = event.num_field("util")
            freq = event.num_field("freq")
            self.processed_events.append(EventMaliUtil(event.pid, event.ts, event.cpu,
                                util, freq))
            return