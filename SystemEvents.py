#!/usr/bin/env python

"""
Tracecmd trace events are wrapped into event objects that can then be handled to construct a task graph of the target
application.

Necessary trace events, such as sched_switch and binder_transaction events, are parsed from the tracecmd events
found in the tracecmd .dat file that is pulled from the target system after the trace has been performed.
These events are all derivatives of the event base class which gives the PID, CPU, name and time stamp of the event.
Interpolation between these events allows for binder transactions to be reconstructed as well as the IPC dependencies
between tasks being able to be co-ordinated with the sched_switch events that track when and where a task is running.
"""

__author__ = "Alex Hoffman"
__copyright__ = "Copyright 2019, Alex Hoffman"
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Alex Hoffman"
__email__ = "alex.hoffman@tum.de"
__status__ = "Beta"

from enum import Enum


class JobType(Enum):
    UNKNOWN = 'U'
    SCHED_SWITCH_IN = 'S'
    SCHED_SWITCH_OUT = 'O'
    FREQ_CHANGE = 'F'
    WAKEUP = 'W'
    IDLE = 'I'
    BINDER_SEND = 'B'
    BINDER_RECV = 'R'


class BinderType(Enum):
    UNKNOWN = 0
    CALL = 1
    REPLY = 2
    ASYNC = 3
    SYNC = 4

    def __str__(self):
        return "%s" % self.name


class ThreadState(Enum):
    UNINTERRUPTIBLE_SLEEP_D = 'D'
    RUNNING_R = 'R'
    INTERRUPTIBLE_SLEEP_S = 'S'
    STOPPED_T = 'T'
    DEAD_X = 'X'
    ZOMBIE_Z = 'Z'

    def __str__(self):
        return str(self.value)


class Event:
    """ All traced events for task graph extraction always provide the PID that is involved with the event,
    the timestamp of the event, the CPU on which the event occurred and the name of the event.
    """

    def __init__(self, pid, ts, name, cpu=0, freq_l=0, freq_b=0, gpu_freq=0, gpu_util=0):
        self.pid = pid
        self.time = ts
        self.cpu = cpu
        self.name = name
        self.cpu_freq = [freq_l, freq_b]
        self.gpu_freq = gpu_freq
        self.gpu_util = gpu_util


class EventSchedSwitch(Event):
    """ Sched switch events are the swapping of two threads on a CPU. The event is tracked by the PIDs
    of the thread being swapped off and the one being swapped in. The state of the thread being swapped
    out is also provided. This is useful to check if a thread was finished executing and in a sleeping
    state when it was swapped off of the CPU.
    """

    def __init__(self, pid, ts, cpu, name, prev_state, next_pid, next_name):
        Event.__init__(self, pid=pid, ts=ts, cpu=cpu, name=name)

        self.prev_state = prev_state
        self.next_pid = next_pid
        self.next_name = next_name


class EventFreqChange(Event):
    """ The frequency of the systems' CPUs is changed when a cpu_freq event occurs
    """

    def __init__(self, pid, ts, cpu, freq, util, target_cpu):
        Event.__init__(self, pid=pid, ts=ts, cpu=cpu, name="freq change")

        self.freq = freq
        self.util = util
        self.target_cpu = target_cpu


class EventWakeup(Event):

    def __init__(self, pid, ts, cpu, name):
        Event.__init__(self, pid=pid, ts=ts, cpu=cpu, name=name)


class EventIdle(Event):
    """ Idle events are used to track how long a certain CPU is no in use and therefore the utilization
    of a thread when executing.

    """

    def __init__(self, ts, cpu, name, state):
        Event.__init__(self, pid=0, ts=ts, cpu=cpu, name=name)

        self.state = state


class EventBinderTransaction(Event):
    """ Binder transactions represent a half (first or second) of an IPC call between two threads.

    """

    def __init__(self, pid, ts, cpu, name, reply, dest_proc, target_pid, flags, code, tran_num):
        Event.__init__(self, pid=pid, ts=ts, cpu=cpu, name=name)

        if reply == 0:

            if flags & 0b1:

                self.trans_type = BinderType.ASYNC

            else:

                self.trans_type = BinderType.CALL

        elif reply == 1:

            self.trans_type = BinderType.REPLY

        else:

            self.trans_type = BinderType.UNKNOWN

        self.dest_proc = dest_proc
        self.target_pid = target_pid
        self.flags = flags
        self.code = code
        self.recv_time = 0
        self.transaction = tran_num


class EventMaliUtil(Event):
    """ Mali GPU metrics are found through the syslogger 'mali' events.

    """

    def __init__(self, pid, ts, cpu, util, freq):
        Event.__init__(self, pid=pid, ts=ts, cpu=cpu, name="mali util")

        self.util = util
        self.freq = freq


class EventTempInfo(Event):
    """ INA sensor temperature values are tracked and stored during system runtime through the
    periodic 'exynos_temp' syslogger events.

    """

    def __init__(self, ts, cpu, big0, big1, big2, big3, little, gpu):
        Event.__init__(self, pid=0, ts=ts, cpu=cpu, name="temp")

        self.big0 = big0
        self.big1 = big1
        self.big2 = big2
        self.big3 = big3
        self.little = little
        self.gpu = gpu


class FreqPowerEvent:
    """ When calculating the power required for a task one needs to know the utilization
    and frequency. The utilization can be assumed to not vary a significant amount during
    the execution of a single job but the frequency should be tracked. A power chunk keeps
    track of the frequency levels used during a job as well as the durations such that the
    total duration of the job can later be divided into periods of different frequency
    use.

    The event stores a snapshot of the system's metrics at the time of the event, before the
    metrics are changed to their new values.
    """

    def __init__(self, ts, cpu, cpu_freq, cpu_util, gpu_freq, gpu_util):
        self.time = ts
        self.cpu = cpu
        self.cpu_frequency = cpu_freq  # Frequency up until the event, not the frequency after the event
        self.gpu_frequency = gpu_freq
        self.cpu_util = cpu_util  # Not really needed
        self.gpu_util = gpu_util


class FirstHalfBinderTransaction:
    """ Binder transactions are often directed to the parent binder thread of a
    system service. The exact PID of the child binder thread that will perform the
    transaction is not known when the first half of the transaction is completed.
    A list of child binder threads is found for the parent binder thread.
    This list is used to match the second half of the binder transaction to any
    pending first halves.
    """

    def __init__(self, event, parent_pid, pidtracer):
        self.parent_pid = parent_pid
        self.child_pids = pidtracer.find_child_binder_threads(parent_pid)
        self.send_event = event


class CompletedBinderTransaction:
    """ A binder transaction is completed in two halves, firstly a transaction is performed to a target
    binder process. This binder process allocates the second half of the transaction to one of its
    child threads.
    """

    def __init__(self, second_half_event, first_half_event=None):

        self.first_half = first_half_event
        self.binder_thread = second_half_event.pid

        if first_half_event:
            self.transaction_type = BinderType.SYNC
            self.duration = second_half_event.time - first_half_event.time
            self.caller_pid = first_half_event.pid
            self.time = first_half_event.time
        else:
            self.transaction_type = BinderType.ASYNC
            self.duration = 0
            self.caller_pid = second_half_event.pid
            self.time = second_half_event.time

        self.target_pid = second_half_event.target_pid
        self.second_half = second_half_event
