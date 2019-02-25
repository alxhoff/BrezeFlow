from adbinterface import adbInterface
from pidtrace import PIDtracer
from pytracer import tracer
from traceprocessor import traceProcessor


def main():
    adbBridge = adbInterface()
    tp = traceProcessor()
    PIDt = PIDtracer(adbBridge, "hillclimb")

    #combo_tracer = tracer(adbBridge,
    #                      "combo",
    #                      events=["binder_transaction", "sched_switch", "cpu_frequency", "mali_utilization_stats"],
    #                      PID_filter=PIDt,
    #                      duration=1)
    #combo_tracer.runTracer()
    #tp.processTracer(combo_tracer, PIDt)
    tp.processTraceFile("combo_tracer.trace", PIDt)
    # tp.filterTracePID(combo_tracer, PIDt, combo_tracer.filename)


if __name__ == '__main__':
    main()
