from pytracer import tracer
from adbinterface import adbInterface
from traceprocessor import traceProcessor
from pid_trace import PIDtracer
from grapher import *

def main():
    adbBridge = adbInterface()
    tp = traceProcessor()
    PIDt  = PIDtracer(adbBridge, "hillclimb")

    wakeup_tracer = tracer(adbBridge,
                            "wakeup",
                            events=["sched_wakeup"],
                            duration=1)
    wakeup_tracer.runTracer()

    tp.processTrace(wakeup_tracer, PIDt)
"""
    #trace schedule
    schedule_tracer = tracer(adbBridge,
                            "schedule",
                            events=["sched_switch"],
                            PID_filter=PIDt,
                            duration=1)
    schedule_tracer.runTracer()

    #tp.filterTracePID(schedule_tracer, PIDt)

    freq_tracer = tracer(adbBridge,
                            "frequency",
                            events=["cpu_frequency"],
                            duration=1)
    freq_tracer.runTracer()

    tp.processTrace(freq_tracer, PIDt)

    idle_tracer = tracer(adbBridge,
                        "idle",
                        events=["cpu_idle"],
                        duration = 1)
    idle_tracer.runTracer()

    tp.processTrace(idle_tracer, PIDt)
"""

if __name__ == '__main__':
    main()
