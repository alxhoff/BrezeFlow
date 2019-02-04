from pytracer import tracer
from adbinterface import adbInterface
from traceprocessor import traceProcessor
from pidtrace import PIDtracer
from grapher import *

def main():
    adbBridge = adbInterface()
    tp = traceProcessor()
    PIDt  = PIDtracer(adbBridge, "hillclimb")

    combo_tracer = tracer(adbBridge,
                        "combo",
                        events=["cpu_frequency","sched_wakeup","sched_switch","cpu_idle"],
                        PID_filter=PIDt,
                        duration=2)
    combo_tracer.runTracer()

    tp.processTrace(combo_tracer, PIDt)

if __name__ == '__main__':
    main()
