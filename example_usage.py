from adbinterface import adbInterface
from pidtrace import PIDtracer
from pytracer import tracer
from traceprocessor import traceProcessor


def main():
    adbBridge = adbInterface()
    tp = traceProcessor()
    PIDt = PIDtracer(adbBridge, "hillclimb")

    # events=["binder_transaction","cpu_frequency","sched_wakeup","sched_switch","cpu_idle"],
    combo_tracer = tracer(adbBridge,
                          "combo",
                          events=["binder_transaction", "sched_switch", "cpu_frequency"],
                          PID_filter=PIDt,
                          duration=1)
    combo_tracer.runTracer()
    tp.processTracer(combo_tracer, PIDt)
    #tp.processTraceFile("combo_tracer.trace", PIDt)
    # tp.filterTracePID(combo_tracer, PIDt, combo_tracer.filename)


if __name__ == '__main__':
    main()
